"""
Insights Hub implementation with ECS Fargate.

This module defines an AWS CDK construct that creates ECS Fargate services
for the Insights Hub frontend and backend components. The services are containerized
and CloudFront is used to provide HTTPS access.
"""

import logging
import os

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


class InsightsHubECS(Construct):
    """
    A construct that creates ECS Fargate services for Insights Hub frontend and backend.

    The services run in containers and are exposed via CloudFront.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.Vpc,
        cluster: ecs.Cluster,
        database_config: dict,
        mcp_server=None,  # Add MCP server parameter
        cognito_config: dict = None,  # Add Cognito configuration parameter
        log_level: str = "INFO",
        **kwargs,
    ):
        """
        Initialize the InsightsHubECS construct.

        Args:
            scope: The parent construct
            id: The construct ID
            vpc: The VPC to deploy the service in
            database_config: Dictionary containing database configuration
            mcp_server: MCP server construct instance (optional)
            cognito_config: Cognito configuration dictionary (optional)
            log_level: Logging level as string (e.g., "INFO", "DEBUG")
            **kwargs: Additional keyword arguments
        """
        super().__init__(scope, id=id, **kwargs)

        self._stack = Stack.of(self)
        stage = self._stack.node.try_get_context("stage") or "dev"

        # Create ECS Cluster for Fargate
        # cluster = ecs.Cluster(self, "Cluster", vpc=vpc)

        # Create security groups for services
        backend_sg = ec2.SecurityGroup(
            self, 
            "BackendSecurityGroup",
            vpc=vpc,
            description="Security group for Insights Hub Backend",
            allow_all_outbound=True
        )
        
        frontend_sg = ec2.SecurityGroup(
            self, 
            "FrontendSecurityGroup",
            vpc=vpc,
            description="Security group for Insights Hub Frontend",
            allow_all_outbound=True
        )
        
        # Allow frontend to access backend
        backend_sg.add_ingress_rule(
            peer=frontend_sg,
            connection=ec2.Port.tcp(3001),
            description="Allow frontend to access backend API"
        )

        # Build Docker image for backend from local Dockerfile
        backend_docker_asset = ecr_assets.DockerImageAsset(
            self,
            "BackendImage",
            directory=os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "src/ecs/insights_hub"
            ),
            file="Dockerfile.backend",
            platform=ecr_assets.Platform.LINUX_AMD64,  # bug fix for m1 chip issue for docker
        )

        # Build Docker image for frontend from local Dockerfile
        frontend_docker_asset = ecr_assets.DockerImageAsset(
            self,
            "FrontendImage",
            directory=os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "src/ecs/insights_hub"
            ),
            file="Dockerfile.frontend",
            platform=ecr_assets.Platform.LINUX_AMD64,  # bug fix for m1 chip issue for docker
        )

        # Environment variables for backend
        backend_environment = {
            "LOG_LEVEL": log_level,
            "PORT": "3001",
            "STAGE": stage,
            "AWS_REGION": Aws.REGION,
            "EMBEDDING_MODEL_ID": self._stack.node.try_get_context("model_embedding"),
            # MCP configuration
            "ENABLE_MCP": "true" if mcp_server else "false",
            "MCP_CLIENT_URL": f"https://{mcp_server.cloudfront_distribution.distribution_domain_name}/mcp" if mcp_server else "",
            "MCP_SECRET_NAME": mcp_server.api_key_secret.secret_name if mcp_server else "",
        }
        backend_environment.update(database_config)
        
        # Add Cognito configuration if provided
        if cognito_config:
            backend_environment.update(cognito_config)

        # Create CloudWatch log groups with retention
        backend_log_group = logs.LogGroup(
            self,
            "BackendLogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        frontend_log_group = logs.LogGroup(
            self,
            "FrontendLogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Create Application Load Balanced Fargate Service for Backend
        self.backend_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "BackendService",
            cluster=cluster,
            memory_limit_mib=2048,
            cpu=1024,
            security_groups=[backend_sg],
            assign_public_ip=True,  # For internet access
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:3001/health || exit 1"],
                interval=Duration.seconds(60),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_docker_image_asset(backend_docker_asset),
                environment=backend_environment,
                container_port=3001,
                enable_logging=True,
                log_driver=ecs.LogDrivers.aws_logs(
                    stream_prefix="insights-hub-backend",
                    # log_retention=logs.RetentionDays.ONE_WEEK,
                    log_group=backend_log_group,
                ),
            ),
            desired_count=1,
            public_load_balancer=True,
            circuit_breaker=ecs.DeploymentCircuitBreaker(enable=True, rollback=True),
            health_check_grace_period=Duration.seconds(120),
            min_healthy_percent=50,
        )

        # Configure backend load balancer health check
        self.backend_service.target_group.configure_health_check(
            path="/health",
            interval=Duration.seconds(60),
            timeout=Duration.seconds(5),
            healthy_threshold_count=2,
            unhealthy_threshold_count=3,
        )

        # Configure ALB timeout settings for streaming responses
        self.backend_service.target_group.set_attribute(
            "deregistration_delay.timeout_seconds", "30"
        )
        # Set idle timeout for long-running requests (streaming)
        self.backend_service.load_balancer.set_attribute(
            "idle_timeout.timeout_seconds", "300"  # 5 minutes
        )

        # Create Application Load Balanced Fargate Service for Frontend
        self.frontend_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "FrontendService",
            cluster=cluster,
            memory_limit_mib=1024,
            cpu=512,
            security_groups=[frontend_sg],
            assign_public_ip=True,  # For internet access
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_docker_image_asset(frontend_docker_asset),
                container_port=80,
                enable_logging=True,
                log_driver=ecs.LogDrivers.aws_logs(
                    stream_prefix="insights-hub-frontend",
                    # log_retention=logs.RetentionDays.ONE_WEEK,
                    log_group=frontend_log_group,
                ),
                environment={
                    "REACT_APP_API_BASE_URL": "/api",  # This will be proxied through CloudFront
                    "REACT_APP_STAGE": stage,
                    "REACT_APP_REGION": Aws.REGION,
                    "BACKEND_URL": f"http://{self.backend_service.load_balancer.load_balancer_dns_name}",  # Pass the backend URL
                },
            ),
            desired_count=1,
            public_load_balancer=True,
            circuit_breaker=ecs.DeploymentCircuitBreaker(enable=True, rollback=True),
            health_check_grace_period=Duration.seconds(120),
            min_healthy_percent=50,
        )

        # Configure frontend load balancer health check
        self.frontend_service.target_group.configure_health_check(
            path="/",
            interval=Duration.seconds(60),
            timeout=Duration.seconds(5),
            healthy_threshold_count=2,
            unhealthy_threshold_count=3,
        )

        # Configure ALB Security Groups to only allow CloudFront access
        self._configure_backend_alb_security_group(vpc)
        self._configure_frontend_alb_security_group(vpc)

        # Generate verification tokens for CloudFront-ALB security
        backend_verification_token = Names.unique_id(self._stack) + "-backend"
        frontend_verification_token = Names.unique_id(self._stack) + "-frontend"

        # Configure backend listener for CloudFront
        backend_listener = self.backend_service.listener
        backend_cfn_listener = backend_listener.node.default_child
        if backend_cfn_listener:
            backend_cfn_listener.default_actions = [
                {
                    "type": "fixed-response",
                    "fixedResponseConfig": {
                        "statusCode": "403",
                        "contentType": "text/plain",
                        "messageBody": "Direct access forbidden",
                    },
                }
            ]

        # Add rules for backend listener
        backend_listener.add_action(
            "HealthCheckRule",
            priority=1,
            conditions=[elbv2.ListenerCondition.path_patterns(["/health"])],
            action=elbv2.ListenerAction.forward([self.backend_service.target_group]),
        )

        backend_listener.add_action(
            "CloudFrontVerification",
            priority=2,
            conditions=[
                elbv2.ListenerCondition.http_header(
                    "X-Origin-Verify", [backend_verification_token]
                )
            ],
            action=elbv2.ListenerAction.forward([self.backend_service.target_group]),
        )

        # Configure frontend listener for CloudFront
        frontend_listener = self.frontend_service.listener
        frontend_cfn_listener = frontend_listener.node.default_child
        if frontend_cfn_listener:
            frontend_cfn_listener.default_actions = [
                {
                    "type": "fixed-response",
                    "fixedResponseConfig": {
                        "statusCode": "403",
                        "contentType": "text/plain",
                        "messageBody": "Direct access forbidden",
                    },
                }
            ]

        frontend_listener.add_action(
            "CloudFrontVerification",
            priority=1,
            conditions=[
                elbv2.ListenerCondition.http_header(
                    "X-Origin-Verify", [frontend_verification_token]
                )
            ],
            action=elbv2.ListenerAction.forward([self.frontend_service.target_group]),
        )

        # Create CloudFront distribution for backend
        self.backend_cloudfront = cloudfront.Distribution(
            self,
            "BackendCloudFront",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.LoadBalancerV2Origin(
                    self.backend_service.load_balancer,
                    protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
                    read_timeout=Duration.seconds(120),  # 增加到2分钟
                    keepalive_timeout=Duration.seconds(60),  # 添加keepalive超时
                    custom_headers={
                        "X-Origin-Verify": backend_verification_token
                    },
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
            ),
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,  # Move to Distribution level
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            enable_logging=True,
        )

        # Create CloudFront distribution for frontend
        self.frontend_cloudfront = cloudfront.Distribution(
            self,
            "FrontendCloudFront",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.LoadBalancerV2Origin(
                    self.frontend_service.load_balancer,
                    protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
                    read_timeout=Duration.seconds(30),
                    custom_headers={
                        "X-Origin-Verify": frontend_verification_token
                    },
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,  # Move to Distribution level
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            enable_logging=True,
        )

        # Add API path behavior to frontend CloudFront to route API requests to backend
        self.frontend_cloudfront.add_behavior(
            "/api/*",
            origins.LoadBalancerV2Origin(
                self.backend_service.load_balancer,
                protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
                read_timeout=Duration.seconds(60),
                custom_headers={
                    "X-Origin-Verify": backend_verification_token
                },
            ),
            allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
            cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
            origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
        )

        # Grant Bedrock permissions to backend service
        self.backend_service.task_definition.task_role.add_to_policy(
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
        
        # Grant permissions to access S3 for content
        self.backend_service.task_definition.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:ListBucket",
                ],
                resources=[
                    f"arn:{Aws.PARTITION}:s3:::*",
                ],
            )
        )
        
        # Grant permissions to access AWS Secrets Manager for MCP API keys
        self.backend_service.task_definition.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "secretsmanager:GetSecretValue",
                ],
                resources=[
                    f"arn:{Aws.PARTITION}:secretsmanager:*:{Aws.ACCOUNT_ID}:secret:MCPServerAPIKey*",
                ],
            )
        )
        
        # Add auto-scaling for the services
        backend_scaling = self.backend_service.service.auto_scale_task_count(
            max_capacity=5,
            min_capacity=1,
        )
        
        backend_scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60),
        )
        
        frontend_scaling = self.frontend_service.service.auto_scale_task_count(
            max_capacity=5,
            min_capacity=1,
        )
        
        frontend_scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60),
        )

        # Output CloudFront URLs
        CfnOutput(
            self,
            "FrontendURL",
            value=f"https://{self.frontend_cloudfront.distribution_domain_name}",
            description="CloudFront URL for the Insights Hub Frontend",
        )

        CfnOutput(
            self,
            "BackendURL",
            value=f"https://{self.backend_cloudfront.distribution_domain_name}/api",
            description="CloudFront URL for the Insights Hub Backend API",
        )
        
        CfnOutput(
            self,
            "BackendDirectURL",
            value=f"http://{self.backend_service.load_balancer.load_balancer_dns_name}",
            description="Direct URL for the Insights Hub Backend (for debugging)",
        )
        
        CfnOutput(
            self,
            "FrontendDirectURL",
            value=f"http://{self.frontend_service.load_balancer.load_balancer_dns_name}",
            description="Direct URL for the Insights Hub Frontend (for debugging)",
        )

    def _configure_backend_alb_security_group(self, vpc: ec2.Vpc):
        """
        Configure backend ALB security group to only allow access from CloudFront IP ranges.
        """
        # Get the backend ALB security group
        backend_alb_security_group = self.backend_service.load_balancer.connections.security_groups[0]
        
        # First, remove all existing ingress rules (including the default 0.0.0.0/0 rule)
        # This requires accessing the underlying CloudFormation resource
        cfn_sg = backend_alb_security_group.node.default_child
        if cfn_sg:
            # Remove all ingress rules by setting an empty list
            cfn_sg.security_group_ingress = []
        
        # Use AWS managed prefix list for CloudFront (recommended)
        try:
            backend_alb_security_group.add_ingress_rule(
                peer=ec2.Peer.prefix_list("pl-3b927c52"),  # AWS managed CloudFront prefix list
                connection=ec2.Port.tcp(80),
                description="Allow HTTP from CloudFront (managed prefix list) - Backend"
            )
        except Exception:
            # Fallback to static IP ranges if prefix list is not available
            self._add_static_cloudfront_ranges(backend_alb_security_group, "Backend")
        
        # Add a rule to allow health checks from within the VPC
        backend_alb_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(80),
            description="Allow health checks from VPC - Backend"
        )

    def _configure_frontend_alb_security_group(self, vpc: ec2.Vpc):
        """
        Configure frontend ALB security group to only allow access from CloudFront IP ranges.
        """
        # Get the frontend ALB security group
        frontend_alb_security_group = self.frontend_service.load_balancer.connections.security_groups[0]
        
        # First, remove all existing ingress rules (including the default 0.0.0.0/0 rule)
        # This requires accessing the underlying CloudFormation resource
        cfn_sg = frontend_alb_security_group.node.default_child
        if cfn_sg:
            # Remove all ingress rules by setting an empty list
            cfn_sg.security_group_ingress = []
        
        # Use AWS managed prefix list for CloudFront (recommended)
        try:
            frontend_alb_security_group.add_ingress_rule(
                peer=ec2.Peer.prefix_list("pl-3b927c52"),  # AWS managed CloudFront prefix list
                connection=ec2.Port.tcp(80),
                description="Allow HTTP from CloudFront (managed prefix list) - Frontend"
            )
        except Exception:
            # Fallback to static IP ranges if prefix list is not available
            self._add_static_cloudfront_ranges(frontend_alb_security_group, "Frontend")
        
        # Add a rule to allow health checks from within the VPC
        frontend_alb_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(80),
            description="Allow health checks from VPC - Frontend"
        )

    def _add_static_cloudfront_ranges(self, security_group, service_name: str):
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
                description=f"Allow HTTP from CloudFront range {i+1} - {service_name}"
            )
