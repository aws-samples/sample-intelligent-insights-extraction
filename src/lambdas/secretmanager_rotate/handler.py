# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# Modified from https://github.com/aws-samples/aws-secrets-manager-rotation-lambdas/blob/master/SecretsManagerRotationTemplate/lambda_function.py
# Adapted to support API key rotation in the format {"api_key": randomstring}

import boto3
import json
import logging
import os
import string
import random

# Configuration settings
CONFIG = {
    "API_KEY_FIELD": os.environ.get(
        "API_KEY_FIELD", "api-key"
    ),  # Field name in the secret JSON
    "API_KEY_LENGTH": int(
        os.environ.get("API_KEY_LENGTH", "16")
    ),  # Length of generated API keys
}

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """Secrets Manager Rotation for API Keys

    This Lambda function rotates API keys stored in AWS Secrets Manager in the format {"api_key": "randomstring"}

    Args:
        event (dict): Lambda dictionary of event parameters. These keys must include the following:
            - SecretId: The secret ARN or identifier
            - ClientRequestToken: The ClientRequestToken of the secret version
            - Step: The rotation step (one of createSecret, setSecret, testSecret, or finishSecret)

        context (LambdaContext): The Lambda runtime information

    Raises:
        ResourceNotFoundException: If the secret with the specified arn and stage does not exist
        ValueError: If the secret is not properly configured for rotation
        KeyError: If the event parameters do not contain the expected keys
    """
    arn = event["SecretId"]
    token = event["ClientRequestToken"]
    step = event["Step"]

    # Setup the client
    service_client = boto3.client(
        "secretsmanager", endpoint_url=os.environ.get("SECRETS_MANAGER_ENDPOINT")
    )

    # Make sure the version is staged correctly
    metadata = service_client.describe_secret(SecretId=arn)
    if not metadata["RotationEnabled"]:
        logger.error("Secret rotation is not enabled for the specified secret")
        raise ValueError("Secret rotation is not enabled for the specified secret")
    versions = metadata["VersionIdsToStages"]
    if token not in versions:
        logger.warning(
            "Secret version %s has no stage for rotation of secret." % token
        )
        raise ValueError(
            "Secret version %s has no stage for rotation of secret %s." % (token, arn)
        )
    if "AWSCURRENT" in versions[token]:
        logger.info(
            "Secret version already set as AWSCURRENT"
        )
        return
    elif "AWSPENDING" not in versions[token]:
        logger.warning(
            "Secret version not set as AWSPENDING for rotation"
        )
        raise ValueError(
            "Secret version not set as AWSPENDING for rotation"
            % (token, arn)
        )

    if step == "createSecret":
        create_secret(service_client, arn, token)

    elif step == "setSecret":
        set_secret(service_client, arn, token)

    elif step == "testSecret":
        test_secret(service_client, arn, token)

    elif step == "finishSecret":
        finish_secret(service_client, arn, token)

    else:
        raise ValueError("Invalid step parameter")


def generate_api_key(length=32):
    """Generate a random API key

    Args:
        length (int): Length of the API key to generate

    Returns:
        string: A random API key
    """
    # Define character set for API key (alphanumeric)
    chars = string.ascii_letters + string.digits

    # Generate random API key
    api_key = "".join(random.choice(chars) for _ in range(length))

    return api_key


def create_secret(service_client, arn, token):
    """Create a new API key secret

    This method first checks for the existence of a secret for the passed in token.
    If one does not exist, it will generate a new API key and put it with the passed in token.

    Args:
        service_client (client): The secrets manager service client
        arn (string): The secret ARN or other identifier
        token (string): The ClientRequestToken associated with the secret version

    Raises:
        ResourceNotFoundException: If the secret with the specified arn and stage does not exist
    """
    # Make sure the current secret exists
    current_secret = service_client.get_secret_value(
        SecretId=arn, VersionStage="AWSCURRENT"
    )

    # Parse the current secret to ensure it's in the expected format
    try:
        current_secret_dict = json.loads(current_secret["SecretString"])
        api_key_field = CONFIG["API_KEY_FIELD"]
        if api_key_field not in current_secret_dict:
            logger.warning(f"Secret {arn} does not contain a {api_key_field} field")
            raise ValueError(f"Secret {arn} does not contain a {api_key_field} field")
    except json.JSONDecodeError:
        logger.warning(f"Secret {arn} is not valid JSON")
        raise ValueError(f"Secret {arn} is not valid JSON")

    # Now try to get the secret version, if that fails, put a new secret
    try:
        service_client.get_secret_value(
            SecretId=arn, VersionId=token, VersionStage="AWSPENDING"
        )
        logger.info("createSecret: Successfully retrieved secret version")
    except service_client.exceptions.ResourceNotFoundException:
        # Generate a new API key
        new_api_key = generate_api_key(CONFIG["API_KEY_LENGTH"])

        # Create the new secret value
        new_secret = json.dumps({CONFIG["API_KEY_FIELD"]: new_api_key})

        # Put the secret
        service_client.put_secret_value(
            SecretId=arn,
            ClientRequestToken=token,
            SecretString=new_secret,
            VersionStages=["AWSPENDING"],
        )
        logger.info("createSecret: Successfully created new secret version")


def set_secret(service_client, arn, token):
    """Set the secret

    This method would typically update the API key in the external service.
    For API keys, this might involve calling an API to update the key.

    If you have a specific service to update, implement the API call here.
    Otherwise, this can be a pass-through for simple API key rotation.

    Args:
        service_client (client): The secrets manager service client
        arn (string): The secret ARN or other identifier
        token (string): The ClientRequestToken associated with the secret version
    """
    # Get the pending secret value
    pending_secret = service_client.get_secret_value(
        SecretId=arn, VersionStage="AWSPENDING", VersionId=token
    )

    # Parse the pending secret
    pending_secret_dict = json.loads(pending_secret["SecretString"])
    new_api_key = pending_secret_dict[CONFIG["API_KEY_FIELD"]]

    # If you need to update an external service with the new API key,
    # implement that logic here. For example:
    #
    # external_service_client = boto3.client('some-service')
    # external_service_client.update_api_key(ApiKey=new_api_key)

    logger.info(f"setSecret: Successfully set new API key for {arn}")


def test_secret(service_client, arn, token):
    """Test the secret

    This method would typically test that the new API key works with the external service.
    For API keys, this might involve making a test API call.

    Args:
        service_client (client): The secrets manager service client
        arn (string): The secret ARN or other identifier
        token (string): The ClientRequestToken associated with the secret version
    """
    # Get the pending secret value
    pending_secret = service_client.get_secret_value(
        SecretId=arn, VersionStage="AWSPENDING", VersionId=token
    )

    # Parse the pending secret
    pending_secret_dict = json.loads(pending_secret["SecretString"])
    new_api_key = pending_secret_dict[CONFIG["API_KEY_FIELD"]]

    # If you need to test the new API key with an external service,
    # implement that logic here. For example:
    #
    # external_service_client = boto3.client('some-service')
    # response = external_service_client.test_api_key(ApiKey=new_api_key)
    # if response['Status'] != 'Valid':
    #     raise ValueError(f"New API key failed validation test")

    logger.info(f"testSecret: Successfully tested new API key for {arn}")


def finish_secret(service_client, arn, token):
    """Finish the secret

    This method finalizes the rotation process by marking the secret version passed in as the AWSCURRENT secret.

    Args:
        service_client (client): The secrets manager service client
        arn (string): The secret ARN or other identifier
        token (string): The ClientRequestToken associated with the secret version

    Raises:
        ResourceNotFoundException: If the secret with the specified arn does not exist
    """
    # First describe the secret to get the current version
    metadata = service_client.describe_secret(SecretId=arn)
    current_version = None
    for version in metadata["VersionIdsToStages"]:
        if "AWSCURRENT" in metadata["VersionIdsToStages"][version]:
            if version == token:
                # The correct version is already marked as current, return
                logger.info(
                    "finishSecret: Version %s already marked as AWSCURRENT"
                    % (version)
                )
                return
            current_version = version
            break

    # Finalize by staging the secret version current
    service_client.update_secret_version_stage(
        SecretId=arn,
        VersionStage="AWSCURRENT",
        MoveToVersionId=token,
        RemoveFromVersionId=current_version,
    )
    logger.info("finishSecret: Successfully updated secret version stage to AWSCURRENT")
