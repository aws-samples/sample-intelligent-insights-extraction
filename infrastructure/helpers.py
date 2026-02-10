#   Copyright 2023 Amazon.com and its affiliates; all rights reserved.
#   This file is Amazon Web Services Content and may not be duplicated or distributed without permission.
import hashlib
import os

import aws_cdk

from aws_cdk import (
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    custom_resources as cr,
    Stack,
    Duration,
    aws_ec2 as ec2,
)
from constructs import Construct


def provision_lambda_function_with_vpc(
    construct,
    lambda_fn_name: str,
    vpc: aws_cdk.aws_ec2.Vpc,
    environment={},
    memory_size=128,
    timeout=60 * 5,
    description="",
    **kwargs,
) -> lambda_.Function:
    """
    Provisions a Lambda function within the specified VPC's private subnets.

    This function creates a new AWS Lambda function with the provided name and configuration.
    The Lambda function is attached to the private subnets of the given VPC, ensuring that
    it can interact securely with other services within the VPC without exposure to the public internet.

    Args:
        construct (Construct): The CDK construct that serves as the parent of this new Lambda function.
        lambda_fn_name (str): The name to assign to the newly created Lambda function.
        vpc (aws_cdk.aws_ec2.Vpc): The VPC where the Lambda function will be provisioned.
        environment (Optional[Dict[str, str]]): A dictionary containing environment variables to set for the Lambda function.
        memory_size (int): The amount of memory, in MB, allocated to the Lambda function.
        timeout (int): The maximum execution duration, in seconds, for the Lambda function.
        description (str): A description of the Lambda function.

    Returns:
        aws_cdk.aws_lambda.Function: The newly created Lambda function.

    """

    # Assuming 'construct' is an instance of the Construct class
    stack = aws_cdk.Stack.of(construct)
    stack_name = stack.stack_name

    if description == "":
        description = f"{stack_name.replace('-', '').title()} function for {lambda_fn_name.title()}"

    function_name = f"{stack_name}-{lambda_fn_name.title().replace('_', '')}"
    # Create a dictionary of function parameters with default values
    function_params = {
        "runtime": lambda_.Runtime.PYTHON_3_12,
        # "allow_public_subnet": True,
        "code": lambda_.Code.from_asset(
            os.path.join(
                os.path.abspath(__file__), f"../../src/lambdas/{lambda_fn_name}"
            )
        ),
        "handler": "handler.lambda_handler",
        "memory_size": memory_size,
        "retry_attempts": 0,
        "timeout": Duration.seconds(timeout),
        "environment": environment,
        "log_retention": logs.RetentionDays.ONE_MONTH,
        "description": description,
        "vpc": vpc,
        "ephemeral_storage_size": aws_cdk.Size.mebibytes(512),
        "role": iam.Role(
            construct,
            f"{stack_name.replace('-', '').title()}{lambda_fn_name.title().replace('_', '')}Role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description=f"Role for lambda {stack.artifact_id} {lambda_fn_name.title().replace('_', '')}",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "CloudWatchLambdaInsightsExecutionRolePolicy"
                ),
                iam.ManagedPolicy(
                    construct,
                    f"{lambda_fn_name.title().replace('_', '')}Policy",
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                                "logs:CreateLogGroup",
                            ],
                            resources=[
                                f"arn:aws:logs:{aws_cdk.Aws.REGION}:{aws_cdk.Aws.ACCOUNT_ID}:"
                                + f"log-group:/aws/lambda/*",
                                f"arn:aws:logs:{aws_cdk.Aws.REGION}:{aws_cdk.Aws.ACCOUNT_ID}:"
                                + f"log-group:/aws/lambda/*:*",
                            ],
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "ec2:CreateNetworkInterface",
                                "ec2:DescribeNetworkInterfaces",
                                "ec2:DescribeSubnets",
                                "ec2:DeleteNetworkInterface",
                                "ec2:AssignPrivateIpAddresses",
                                "ec2:UnassignPrivateIpAddresses",
                            ],
                            resources=[
                                "*",
                            ],
                        ),
                    ],
                ),
            ],
        ),
    }

    function_params.update(**kwargs)

    function_params.setdefault("layers", [])

    fn = lambda_.Function(
        construct,
        f"lambda_{lambda_fn_name.title().replace('_', '')}",
        **function_params,
    )

    return fn
