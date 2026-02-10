import logging
import os
from typing import Dict, Optional, Union

from aws_cdk import CfnOutput
from constructs import Construct
from aws_cdk import Stack, RemovalPolicy, Duration, Aws
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_notifications as s3n
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_logs as logs
from aws_cdk import aws_lambda_event_sources as lambda_events
from aws_cdk import aws_ecs as ecs

from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets


from .helpers import provision_lambda_function_with_vpc
from .opensearch_serverless import OpenSearchServerless
from .vpc_stack import VPCStack
from .mcp_server import MCPServerECS
from .insights_hub import InsightsHubECS
from .cognito import CognitoPool


class MyStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        bucket = self.create_data_bucket(bucket_name="SourceBucket")

        # crate a VPC
        vpc_stack = VPCStack(self)
        self.vpc = vpc_stack.get_vpc()

        self.third_parth_layer = self._provision_third_party_layer()

        # create a lambda function in the vpc
        self.summary_lambda = provision_lambda_function_with_vpc(
            self,
            "idea_extraction",
            vpc=vpc_stack.get_vpc(),
            layers=[self.third_parth_layer],
            environment={"LOG_LEVEL": str(self.get_stack_log_level())},
            memory_size=1024,
            timeout=60 * 15,
        )

        self.enable_lambda_function_with_bedrock(self.summary_lambda)

        self.summary_lambda.add_environment(
            "EMBEDDING_MODEL", self.node.try_get_context("model_embedding")
        )

        self.summary_lambda.add_environment(
            "EXTRACTION_MODEL", self.node.try_get_context("model_extraction")
        )

        bucket.grant_read_write(self.summary_lambda)

        # Create SQS queue
        waiting_process_queue = sqs.Queue(
            self,
            "DocumentQueue",
            queue_name=f"{construct_id.lower()}-documents-queue",
            visibility_timeout=Duration.seconds(900),  # Match Lambda timeout
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            # For production, consider a Dead Letter Queue
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=5,
                queue=sqs.Queue(
                    self,
                    "DeadLetterQueue",
                    queue_name=f"{construct_id.lower()}-documents-dlq",
                    retention_period=Duration.days(14),
                ),
            ),
        )

        # Grant S3 permission to send messages to SQS
        waiting_process_queue.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["sqs:SendMessage"],
                principals=[iam.ServicePrincipal("s3.amazonaws.com")],
                resources=[waiting_process_queue.queue_arn],
                conditions={"ArnLike": {"aws:SourceArn": bucket.bucket_arn}},
            )
        )

        # Set up S3 notification to SQS for metadata.json files
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.SqsDestination(waiting_process_queue),
            s3.NotificationKeyFilter(
                suffix="metadata.json"  # Only trigger for files ending with .json
            ),
        )

        # Set up S3 notification to SQS for .txt files
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.SqsDestination(waiting_process_queue),
            s3.NotificationKeyFilter(
                suffix=".txt"  # Only trigger for files ending with .txt
            ),
        )

        # Set up S3 notification to SQS for .pdf files
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.SqsDestination(waiting_process_queue),
            s3.NotificationKeyFilter(
                suffix=".pdf"  # Only trigger for files ending with .pdf
            ),
        )

        sqs_event_source = lambda_events.SqsEventSource(
            waiting_process_queue,
            batch_size=1,  # Messages per Lambda invocation
            max_concurrency=2,
            max_batching_window=Duration.seconds(
                0
            ),  # Wait to collect messages before invoking
            report_batch_item_failures=True,  # Enable partial batch failure handling
        )

        # Add the configured event source to the Lambda function
        self.summary_lambda.add_event_source(sqs_event_source)

        # Create the JavaScript HTML Readability Lambda function
        self.readability_lambda = self._create_js_readability_lambda(
            "JSHTMLReadability",
            vpc=vpc_stack.get_vpc(),
            log_level=str(self.get_stack_log_level()),
        )

        self.summary_lambda.add_environment(
            "HTML_READABILITY_FUNCTION_NAME", self.readability_lambda.function_name
        )

        self.readability_lambda.grant_invoke(self.summary_lambda)
        bucket.grant_read(self.readability_lambda)

        # create opensearch serverless
        database_config = {}

        index_name = "content"
        self.database = OpenSearchServerless(
            self, "OpenSearchServerless", vpc=vpc_stack.get_vpc(), index_name=index_name
        )
        database_config["OPENSEARCH_ENDPOINT"] = (
            self.database.collection.attr_collection_endpoint
        )
        database_config["OPENSEARCH_INDEX"] = index_name
        database_config["S3_BUCKET"] = bucket.bucket_name

        # grant lambda function access to the database and add the environment
        self.database.grant_connection(role=self.summary_lambda.role)

        for key, value in database_config.items():
            self.summary_lambda.add_environment(key, value)

        cognito = CognitoPool(self, construct_id)

        # Create Cognito configuration
        cognito_config = {
            "COGNITO_USER_POOL_ID": cognito.get_user_pool_id(),
            "COGNITO_CLIENT_ID": cognito.get_user_pool_client_id(),
            "COGNITO_REGION": Aws.REGION,
        }

        # Create ECS Cluster for Fargate
        cluster = ecs.Cluster(
            self,
            "Cluster",
            cluster_name=f"{construct_id}-cluster",
            vpc=vpc_stack.get_vpc(),
        )

        # Create the MCP Server Lambda with Function URL
        self.mcp_server = MCPServerECS(
            self,
            "MCPServer",
            "mcp_server_ideas",
            vpc=vpc_stack.get_vpc(),
            cluster=cluster,
            database_config=database_config,
            log_level=self.get_stack_log_level(),
        )

        self.database.grant_connection(
            self.mcp_server.service.task_definition.task_role
        )

        # Create the Insights Hub with frontend and backend services
        self.insights_hub = InsightsHubECS(
            self,
            "InsightsHub",
            vpc=vpc_stack.get_vpc(),
            cluster=cluster,
            database_config=database_config,
            mcp_server=self.mcp_server,  # Pass MCP server reference
            cognito_config=cognito_config,  # Pass Cognito configuration
            log_level="INFO",  # Use string value instead of numeric
        )

        # Grant database access to the Insights Hub backend service
        self.database.grant_connection(
            self.insights_hub.backend_service.task_definition.task_role
        )

        self.rss_sync_function = self._provision_rss_scraper(bucket.bucket_name)

        bucket.grant_read_write(self.rss_sync_function.role)

        # Create EventBridge rule for scheduling
        schedule_rule = events.Rule(
            self,
            "ScheduledLambdaRule",
            schedule=events.Schedule.rate(Duration.minutes(15)),
        )
        
        # create a sample for how to call rss sync for demonstration purpose
        schedule_rule.add_target(
            targets.LambdaFunction(
                self.rss_sync_function,
                event=events.RuleTargetInput.from_object(
                    {
                        "rss_feed_url": "https://aws.amazon.com/blogs/aws/feed/",
                        "hours_back": 24,
                        "download_images": True,
                    }
                ),
            )
        )


    def _create_js_readability_lambda(
        self, id: str, vpc, log_level="INFO"
    ) -> lambda_.Function:
        """
        Creates a Lambda function for HTML readability processing using JavaScript.

        Args:
            id: Construct ID
            vpc: VPC to deploy the Lambda in
            log_level: Logging level for the Lambda function

        Returns:
            lambda_.Function: The created Lambda function
        """
        # Create the Lambda function using Node.js runtime
        readability_lambda = lambda_.Function(
            self,
            id,
            runtime=lambda_.Runtime.NODEJS_LATEST,
            handler="index.handler",
            code=lambda_.Code.from_asset(
                os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "src/lambdas/html_readability",
                )
            ),
            timeout=Duration.seconds(60),
            memory_size=512,
            environment={
                "LOG_LEVEL": log_level,
            },
            log_retention=logs.RetentionDays.ONE_MONTH,
            vpc=vpc,
        )

        return readability_lambda

    def _provision_rss_scraper(self, bucket_name: str) -> lambda_.Function:

        browser_ues_layer = lambda_.LayerVersion(
            self,
            "AgentCoreBrowser",
            compatible_architectures=[lambda_.Architecture.X86_64],
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="browser use binary layer",
            code=lambda_.AssetCode(
                os.path.join(
                    os.path.abspath(__file__),
                    "../../src/lambda_layers/agentcore_browser/layer.zip",
                )
            ),
        )

        # create a lambda function in the vpc
        lambda_function = provision_lambda_function_with_vpc(
            self,
            "rss_sync",
            vpc=self.vpc,
            layers=[browser_ues_layer],
            runtime=lambda_.Runtime.PYTHON_3_12,
            environment={
                "LOG_LEVEL": str(self.get_stack_log_level()),
                "S3_BUCKET": bucket_name,
                "BROWSER_REGION": Aws.REGION,
            },
            memory_size=1024,
            timeout=60 * 15,
        )

        lambda_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:*"],
                resources=[
                    "arn:aws:bedrock-agentcore:us-west-2:aws:browser/aws.browser.v1",
                    "arn:aws:bedrock-agentcore:us-east-1:aws:browser/aws.browser.v1",
                ],
                effect=iam.Effect.ALLOW,
            ),
        )

        return lambda_function

    def _provision_third_party_layer(self) -> lambda_.LayerVersion:
        """
        Creates and returns a Lambda layer for third-party dependencies.

        This method provisions a new AWS Lambda Layer, intended to provide
        additional libraries or dependencies external to the Lambda function
        itself. The layer is specifically configured for a Python 3.12 runtime
        and is compatible with x86_64 architecture.

        The layer's content is loaded from a zip file located relative to this
        script's directory, specifically in the 'lambda_layers/third_party' subdirectory.

        Returns:
            lambda_.LayerVersion: An object representing the created Lambda layer,
            ready to be attached to Lambda functions within the same AWS environment.

        Raises:
            FileNotFoundError: If the layer zip file does not exist at the specified path.
            AWS CDK specific exceptions related to resource creation and configuration might also be raised.
        """
        layer = lambda_.LayerVersion(
            self,
            "ThirdPartyLayer",
            compatible_architectures=[lambda_.Architecture.X86_64],
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="third party database binary layer",
            code=lambda_.AssetCode(
                os.path.join(
                    os.path.abspath(__file__),
                    "../../src/lambda_layers/third_party/layer.zip",
                )
            ),
        )

        return layer

    def get_stack_log_level(self) -> int:
        """
        Get the numeric log level from stack context.

        Returns:
            int: The numeric logging level (10 for DEBUG, 20 for INFO, etc.)
                  Defaults to INFO (20) if not specified or invalid
        """
        # Default log level
        default_level: int = logging.INFO  # 20

        # Create mapping using Python's built-in logging _nameToLevel dict
        # This automatically includes all standard levels
        log_level_map: Dict[str, int] = logging._nameToLevel.copy()

        # Add common aliases that aren't in the standard mapping
        log_level_map.update({"WARN": logging.WARNING, "FATAL": logging.CRITICAL})

        # Get log level from context
        log_level_input: Optional[Union[str, int]] = self.node.try_get_context(
            "log_level"
        )

        # If no log level specified, return default
        if not log_level_input:
            return default_level

        # Handle string input (case-insensitive)
        if isinstance(log_level_input, str):
            # Normalize the string (uppercase and strip whitespace)
            normalized_level: str = log_level_input.upper().strip()

            # Check if it's in our mapping
            if normalized_level in log_level_map:
                return log_level_map[normalized_level]
        return default_level

    def enable_lambda_function_with_bedrock(self, fn: lambda_.Function) -> None:
        """
        Add Bedrock permissions to a Lambda function.

        Args:
            fn: The Lambda function to grant Bedrock permissions to
        """
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=[
                    f"arn:{Aws.PARTITION}:bedrock:*::foundation-model/*",
                    f"arn:{Aws.PARTITION}:bedrock:*:{Aws.ACCOUNT_ID}:inference-profile/*",
                ],
                effect=iam.Effect.ALLOW,
            ),
        )

    def create_data_bucket(self, bucket_name: str) -> s3.Bucket:
        """
        Creates two S3 buckets: one for storing data and another for storing access logs.

        The data bucket is configured with server-side encryption, SSL enforcement, auto-deletion of objects,
        and a lifecycle rule to expire objects after 180 days. The log bucket is configured to be automatically
        deleted when the stack is destroyed.

        Parameters:
            bucket_name (str): The name of the data bucket to be created. This name must be globally unique.

        Returns:
            s3.Bucket: The newly created data bucket configured with the specified properties.
        """
        # create s3 bucket for data storage
        # Bucket for storing logs
        log_bucket = s3.Bucket(
            self,
            f"LogBucket{bucket_name}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    enabled=True,
                    expiration=Duration.days(180),
                )
            ],
        )

        data_bucket = s3.Bucket(
            self,
            bucket_name,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    enabled=True,
                    expiration=Duration.days(360),
                )
            ],
            server_access_logs_bucket=log_bucket,
            server_access_logs_prefix="access-logs/",
        )

        # Output the bucket name and readability Lambda function name
        CfnOutput(
            self,
            "BucketName",
            value=data_bucket.bucket_name,
            description="Name of the S3 bucket where crawled HTML files can be uploaded for summarization",
        )
        return data_bucket
