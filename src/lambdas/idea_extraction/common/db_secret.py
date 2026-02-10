#   Copyright 2025 Amazon.com and its affiliates; all rights reserved.
#   This file is Amazon Web Services Content and may not be duplicated or distributed without permission.

"""
This module provides utilities for accessing AWS Secrets Manager to retrieve
confidential information like database credentials. It defines functions to
get a Secrets Manager client, fetch a secret, and establish a connection to
an RDS instance using the retrieved secret.

Functions:
    get_secrets_manager_client(region_name): Returns a boto3 Secrets Manager client.
    get_secret(): Retrieves the secret from AWS Secrets Manager.
    get_rds_connection(): Establishes a connection to an RDS instance.
"""


import json
import os

import boto3

from botocore.exceptions import ClientError

# Cache the client to avoid recreating it on each function call
_SECRETS_MANAGER_CLIENT = None

_opensearch_client = None


def get_opensearch_client():
    """
    Create and return an OpenSearch client using environment variables
    This is implemented as a singleton pattern to avoid creating multiple clients.

    This function creates an authenticated connection to the OpenSearch
    serverless collection using AWS SigV4 authentication. It reads the
    endpoint from environment variables.

    Returns:
        OpenSearch: Configured OpenSearch client ready to use

    Environment Variables:
        OPENSEARCH_ENDPOINT: The host endpoint for OpenSearch
        AWS_REGION: The AWS region (defaults to us-east-1)
    """
    from opensearchpy import RequestsHttpConnection, AWSV4SignerAuth, OpenSearch

    global _opensearch_client

    # Return existing client if already initialized
    if _opensearch_client is not None:
        return _opensearch_client
    service = os.environ.get("DATABASE_CHOICE", "aoss")
    host = os.environ.get("OPENSEARCH_ENDPOINT")
    region = os.environ.get("AWS_REGION", "us-east-1")

    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, region, service)

    _opensearch_client = OpenSearch(
        hosts=[{"host": host[8:], "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=300,  # Increased timeout for potentially large operations
        pool_maxsize=20,
    )

    return _opensearch_client
