"""
Model Context Protocol (MCP) Server implementation with ECS Fargate.

This module defines an AWS CDK construct that creates an ECS Fargate service
for serving MCP requests. The service is containerized and uses API key
authentication via AWS Secrets Manager. CloudFront is used to provide HTTPS.
"""

import logging
import os

import logging

from aws_cdk import (
    aws_secretsmanager as secretsmanager,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_ecr_assets as ecr_assets,
    aws_ecs_patterns as ecs_patterns,
    aws_logs as logs,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    CfnOutput,
    RemovalPolicy,
    aws_elasticloadbalancingv2 as elbv2,
    Stack,
    Aws,
    Duration,
    Fn,
    Names,
)
from constructs import Construct
from infrastructure.helpers import provision_lambda_function_with_vpc

class MCPServerECS(Construct):
    """
    A construct that creates an ECS Fargate service for MCP Server.

    The service runs in a container and uses API key authentication
    via AWS Secrets Manager.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        source_folder: str,
        vpc: ec2.Vpc,
        cluster: ecs.Cluster,
        database_config: dict,
        log_level: int = logging.INFO,
        **kwargs,
    ):
        """
        Initialize the MCPServerECS construct.

        Args:
            scope: The parent construct
            id: The construct ID
            source_folder: The name of the function/service
            vpc: The VPC to deploy the service in
            database_config: Dictionary containing database configuration
            log_level: Logging level as integer (e.g., logging.INFO, logging.DEBUG)
            **kwargs: Additional keyword arguments
        """
        super().__init__(scope, id=id, **kwargs)

        self._stack = Stack.of(self)
        self.vpc = vpc
        self.cluster = cluster

        # Create a secret for the API key
        self.api_key_secret = secretsmanager.Secret(
            self,
            "APIKey",
            description="API Key for MCP Server",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_characters='"@/\\',
                generate_string_key="api-key",
                secret_string_template="{}",
            ),
            removal_policy=RemovalPolicy.DESTROY,  # Use RETAIN for production
        )

        self.api_key_secret_rotate_lambda = self._create_rotation_lambda()

        self.api_key_secret.add_rotation_schedule(
            f"Rotate",
            automatically_after=Duration.days(30),
            rotation_lambda=self.api_key_secret_rotate_lambda,
        )

        self.api_key_secret.grant_write(self.api_key_secret_rotate_lambda)
        self.api_key_secret.grant_read(self.api_key_secret_rotate_lambda)

        # Create ECS Cluster for Fargate
        # cluster = ecs.Cluster(self, "Cluster", cluster_name=, vpc=vpc)

        # Build Docker image from local Dockerfile
        docker_asset = ecr_assets.DockerImageAsset(
            self,
            "Image",
            directory=os.path.join(
                os.path.dirname(os.path.dirname(__file__)), f"src/ecs/{source_folder}"
            ),
            platform=ecr_assets.Platform.LINUX_AMD64,  # bug fix for m1 chip issue for docker
        )

        task_environment = {
            "LOG_LEVEL": str(log_level),
            "API_SECRET_NAME": self.api_key_secret.secret_name,
            "EMBEDDING_MODEL_ID": self._stack.node.try_get_context("model_embedding"),
            "STAGE": self._stack.node.try_get_context("stage"),
            "AWS_REGION": Aws.REGION,
        }
        task_environment.update(database_config)

        # Create Application Load Balanced Fargate Service
        self.service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "Service",
            cluster=cluster,
            memory_limit_mib=2048,
            cpu=1024,  # Adding CPU units for Fargate
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:3000/health || exit 1"],
                interval=Duration.seconds(60),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(
                    60
                ),  # Give the container time to start up
            ),
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_docker_image_asset(docker_asset),
                environment=task_environment,
                container_port=3000,  # Port your application listens on
                enable_logging=True,
                log_driver=ecs.LogDrivers.aws_logs(
                    stream_prefix="mcp-server",
                    log_retention=logs.RetentionDays.ONE_WEEK,
                ),
            ),
            desired_count=1,  # Fixed number of tasks
            public_load_balancer=True,
            circuit_breaker=ecs.DeploymentCircuitBreaker(enable=True, rollback=True),
            health_check_grace_period=Duration.seconds(120),
            min_healthy_percent=50,
        )

        # Configure load balancer health check
        self.service.target_group.configure_health_check(
            path="/health",
            interval=Duration.seconds(60),
            timeout=Duration.seconds(5),
            healthy_threshold_count=2,
            unhealthy_threshold_count=3,
        )

        # Configure ALB Security Group to only allow CloudFront access
        self._configure_alb_security_group()

        # Generate a verification token for CloudFront-ALB security

        verification_token = Names.unique_id(self._stack)
        listener = self.service.listener
        # First, remove all default actions by using node.default_child
        # This accesses the underlying CFN resource
        cfn_listener = listener.node.default_child
        if cfn_listener:
            # Set the default action to block direct access
            cfn_listener.default_actions = [
                {
                    "type": "fixed-response",
                    "fixedResponseConfig": {
                        "statusCode": "403",
                        "contentType": "text/plain",
                        "messageBody": "Direct access forbidden",
                    },
                }
            ]

        # Add a rule to allow health check requests with high priority
        listener.add_action(
            "HealthCheckRule",
            priority=1,  # Highest priority (lowest number)
            conditions=[elbv2.ListenerCondition.path_patterns(["/health"])],
            action=elbv2.ListenerAction.forward([self.service.target_group]),
        )

        # Add a rule to verify requests from CloudFront with second priority
        listener.add_action(
            "CloudFrontVerification",
            priority=2,  # Second highest priority
            conditions=[
                elbv2.ListenerCondition.http_header(
                    "X-Origin-Verify", [verification_token]
                )
            ],
            action=elbv2.ListenerAction.forward([self.service.target_group]),
        )

        # No need for a catch-all rule since we've set the default action to block access

        # Create CloudWatch log group for CloudFront logs


        # Create CloudFront distribution with ALB as origin
        self.cloudfront_distribution = cloudfront.Distribution(
            self,
            "CloudFrontDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.LoadBalancerV2Origin(
                    self.service.load_balancer,
                    protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
                    read_timeout=Duration.seconds(60),  # Increased for streaming
                    custom_headers={
                        "X-Origin-Verify": verification_token  # Add verification token
                    },
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,  # Redirect HTTP to HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,  # Must disable caching for SSE
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,  # Forward all headers including auth
            ),
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,  # Move to Distribution level
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,  # Use only North America and Europe
            enable_logging=True,  # enable S3 logging since we're using CloudWatch
        )



        # Grant the task role permission to read the API key secret
        # Task Role = Permissions for your application running inside containers
        # Execution Role = Permissions for ECS to set up and manage your containers
        self.api_key_secret.grant_read(self.service.task_definition.task_role)
        self.api_key_secret.grant_read(self.service.task_definition.execution_role)

        self.service.task_definition.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=[
                    f"arn:{Aws.PARTITION}:bedrock:*::foundation-model/*",
                    f"arn:{Aws.PARTITION}:bedrock:*:{Aws.ACCOUNT_ID}:inference-profile/*",
                ],
            )
        )

        # Output the API key secret name and service URL
        CfnOutput(
            self,
            "APIKeySecretName",
            value=self.api_key_secret.secret_name,
            description="Name of the secret containing the API key",
        )

        # Add CloudFront URL as output
        CfnOutput(
            self,
            "CloudFrontURL",
            value=f"https://{self.cloudfront_distribution.distribution_domain_name}/mcp",
            description="CloudFront HTTPS URL of the MCP Server",
        )

    def _create_rotation_lambda(self):
        rotate_lambda = provision_lambda_function_with_vpc(
            self._stack, "secretmanager_rotate", self.vpc, memory_size=256
        )

        rotate_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetRandomPassword"],
                resources=["*"],
            )
        )

        return rotate_lambda

    def _configure_alb_security_group(self):
        """
        Configure ALB security group to only allow access from CloudFront IP ranges.
        This adds an extra layer of security beyond the HTTP header verification.
        """
        # Get the ALB security group
        alb_security_group = self.service.load_balancer.connections.security_groups[0]
        
        # First, remove all existing ingress rules (including the default 0.0.0.0/0 rule)
        # This requires accessing the underlying CloudFormation resource
        cfn_sg = alb_security_group.node.default_child
        if cfn_sg:
            # Remove all ingress rules by setting an empty list
            cfn_sg.security_group_ingress = []
        
        # Method 1: Use AWS managed prefix list for CloudFront (recommended)
        # This automatically updates when AWS changes CloudFront IP ranges
        try:
            # Add rule using AWS managed prefix list for CloudFront
            alb_security_group.add_ingress_rule(
                peer=ec2.Peer.prefix_list("pl-3b927c52"),  # AWS managed CloudFront prefix list
                connection=ec2.Port.tcp(80),
                description="Allow HTTP from CloudFront (managed prefix list)"
            )
        except Exception:
            # Fallback to static IP ranges if prefix list is not available
            self._add_static_cloudfront_ranges(alb_security_group)
        
        # Add a rule to allow health checks from within the VPC (for ALB health checks)
        alb_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(80),
            description="Allow health checks from VPC"
        )
    
    def _add_static_cloudfront_ranges(self, security_group):
        """
        Fallback method to add static CloudFront IP ranges.
        These should be updated periodically from https://ip-ranges.amazonaws.com/ip-ranges.json
        """
        # Current CloudFront IPv4 ranges (update these periodically)
        cloudfront_ipv4_ranges = [
            "13.32.0.0/15",
            "13.35.0.0/16", 
            "18.238.0.0/15",
            "52.46.0.0/18",
            "52.82.128.0/19",
            "52.84.0.0/15",
            "54.182.0.0/16",
            "54.192.0.0/16",
            "54.230.0.0/16",
            "54.239.128.0/18",
            "54.239.192.0/19",
            "54.240.128.0/18",
            "99.84.0.0/16",
            "130.176.0.0/16",
            "204.246.164.0/22",
            "204.246.168.0/22",
            "204.246.174.0/23",
            "204.246.176.0/20",
            "205.251.192.0/19",
            "205.251.249.0/24",
            "205.251.250.0/23",
            "205.251.252.0/23",
            "205.251.254.0/24",
        ]
        
        # Add rules for each CloudFront IP range
        for i, cidr in enumerate(cloudfront_ipv4_ranges):
            security_group.add_ingress_rule(
                peer=ec2.Peer.ipv4(cidr),
                connection=ec2.Port.tcp(80),
                description=f"Allow HTTP from CloudFront range {i+1}"
            )