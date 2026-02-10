"""
This module provides functionality for interacting with the Bedrock Runtime service to
convert sentences to numerical embeddings using a specified machine learning model.

It includes the following functions:

- `get_bedrock_runtime_client`: Initializes and retrieves a singleton instance of the
  Bedrock Runtime client for AWS.
- `get_embedding_from_text`: Converts a given sentence into a numerical embedding by
  calling the Bedrock embedding model.

Environment Variables:
    REGION_NAME (str): The AWS region where the Bedrock Runtime service is accessed.
        Defaults to "us-east-1" if not specified.

    EMBEDDING_MODEL (str): The identifier of the embedding model to use. Must be
        specified as an environment variable; otherwise, `get_embedding_from_text`
        raises a ValueError.

Usage:
    Ensure the environment variables are set prior to invoking the functions within
    this module. For instance, in a Unix-like shell, you might use:

    ```sh
    export REGION_NAME='us-west-2'
    export EMBEDDING_MODEL='my-embedding-model'
    ```

    Then the module's functions can be called from Python code as follows:

    ```python
    embedding = get_embedding_from_text("Sample text to convert into an embedding.")
    ```
"""

import json
import os

import boto3
from botocore.config import Config

# Singleton instance of the Bedrock Runtime client, initialized as None and created when needed.
_BEDROCK_RUNTIME_CLIENT = None


def get_bedrock_runtime_client():
    """Get or create a Bedrock Runtime client.

    This function checks if the Bedrock Runtime client has already been created. If not,
    it initializes a new client with the specified AWS region, which defaults to "us-east-1"
    unless overridden by the 'REGION_NAME' environment variable.

    Returns:
        A boto3 client for the Bedrock Runtime service.
    """
    global _BEDROCK_RUNTIME_CLIENT

    config = Config(
        read_timeout=300,  # set the timeout for using bedrock as 300 seconds
    )

    if _BEDROCK_RUNTIME_CLIENT is None:

        _BEDROCK_RUNTIME_CLIENT = boto3.client("bedrock-runtime", config=config)

    return _BEDROCK_RUNTIME_CLIENT


def get_embedding_from_text(text):
    """
    Convert a sentence to an embedding

    In this POC, we call the Bedrock embedding model
    Args:
        text: a sample text

    Returns:
        np.array: a vector that converted by embedding model

    """
    embedding_model = os.environ.get("EMBEDDING_MODEL_ID")
    if not embedding_model:
        raise ValueError("Error: 'EMBEDDING_MODEL_ID' environment variable is missing.")

    if "cohere" in embedding_model:

        body = {
            "texts": [text[:2048]],
            "input_type": "search_document",
            "embedding_types": ["int8", "float"],
        }
        # invoke_bedrock
        response = get_bedrock_runtime_client().invoke_model(
            contentType="application/json",
            accept="*/*",
            modelId=embedding_model,
            body=json.dumps(body),
        )

        response_body = json.loads(response.get("body").read())
        embeddings = response_body.get("embeddings")
        for i, embedding_type in enumerate(embeddings):
            return embeddings[embedding_type][0]

    else:
        body = {"inputText": text}
    # invoke_bedrock
    response = get_bedrock_runtime_client().invoke_model(
        contentType="application/json",
        accept="*/*",
        modelId=embedding_model,
        body=json.dumps(body),
    )

    response_body = json.loads(response.get("body").read())

    return response_body["embedding"]
