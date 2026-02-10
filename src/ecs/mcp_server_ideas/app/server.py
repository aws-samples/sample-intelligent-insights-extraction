import json
import os
import logging
from typing import Dict, Any, Annotated, Optional, List
import boto3
from opensearchpy import RequestsHttpConnection, AWSV4SignerAuth, OpenSearch
from pydantic import Field
from fastmcp import FastMCP

import traceback

from starlette.responses import JSONResponse

from token_verifier import SecretManagerTokenVerifier

# Configure logging
mcp_server_logger = logging.getLogger("mcp-server")
mcp_server_logger.setLevel(logging.DEBUG)




verifier = SecretManagerTokenVerifier(required_scopes=["read:data"])
# Create the MCP server with proper name
mcp_server = FastMCP(
    "MCP API Server",
    dependencies=["pandas", "numpy"],
    auth=verifier,
    instructions="Model Context Protocol server for API data access",
)
# Singleton instance for OpenSearch client
_opensearch_client = None

EMBEDDING_MODEL_ID = os.environ.get("EMBEDDING_MODEL_ID")

# Define path to your data file
_sample_df = None

# Define common source fields for OpenSearch queries
DOCUMENT_SOURCE_FIELDS: List[str] = [
    "summary",
    "content",
    "document_type",
    "s3_bucket_file",
]

# Environment variables for OpenSearch indices and Bedrock model
OPENSEARCH_DOCUMENT_INDEX = os.getenv("OPENSEARCH_INDEX", "content")  # Index for storing document data and embeddings


def remove_vector_fields(obj):
    """
    Recursively remove any keys containing '_vector' from a dictionary
    """
    if isinstance(obj, dict):
        return {
            k: remove_vector_fields(v) for k, v in obj.items() if "_vector" not in k
        }
    elif isinstance(obj, list):
        return [remove_vector_fields(item) for item in list(obj)]
    else:
        return obj


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
    global _opensearch_client

    # Return existing client if already initialized
    if _opensearch_client is not None:
        return _opensearch_client

    host = os.environ.get("OPENSEARCH_ENDPOINT")
    region = os.environ.get("AWS_REGION", "us-east-1")

    service = "aoss"  # Amazon OpenSearch Serverless service name for SigV4
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

# add health check
@mcp_server.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "healthy", "service": "mcp-server"})

# Add application resources
@mcp_server.resource("config://app")
def get_app_config() -> Dict[str, Any]:
    """Return application configuration information"""
    return {
        "version": os.environ.get("APP_VERSION", "1.0.0"),
        "environment": os.environ.get("STAGE", "production"),
        "embedding_model_id": EMBEDDING_MODEL_ID,
        "service": "mcp-api-server",
    }


@mcp_server.tool(
    description="Search for documents with similar content based on a text query. This function matches your query against document summaries that capture the main points of each document. "
)
async def find_documents_with_similar_summaries(
    query_text: Annotated[
        str,
        Field(
            description="Text content to use as search query for finding similar documents (required)",
            examples=[
                "Xiao Mi's new design idea ",
            ],
        ),
    ],
    industry: Annotated[
        Optional[str],
        Field(
            description="Filter results by industry (options are, 'furniture', 'fashion', 'car')",
            examples=["car"],
        ),
    ] = None,
    limit: Annotated[
        int,
        Field(
            description="Maximum number of results to return",
            examples=[5, 10, 20],
            default=5,
        ),
    ] = 5,
    offset: Annotated[
        int,
        Field(
            description="Number of results to skip (for pagination)",
            examples=[0, 10, 20],
            default=0,
        ),
    ] = 0,
) -> Dict[str, Any]:
    """
    Find documents with summaries similar to the query with integrated reranking.
    Uses hybrid search (combining vector and text search) and reranks results using Cohere.
    """

    mcp_server_logger.info(
        f"Searching documents with similar summaries to query: {query_text}"
    )
    try:
        # Initialize Elasticsearch client
        client = get_opensearch_client()

        # Simplified: use actual limit for better performance

        # Use text-only search for better performance (skip embedding generation)
        combined_query = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "multi_match": {
                                "query": query_text,
                                "fields": ["summary^2", "content"],  # Boost summary field
                                "type": "best_fields",
                                "fuzziness": "AUTO",
                            }
                        },
                        {
                            "match": {
                                "summary": {
                                    "query": query_text,
                                    "boost": 3.0  # Higher boost for summary matches
                                }
                            }
                        }
                    ],
                    "minimum_should_match": 1,
                    "filter": [],
                }
            },
            "_source": ["summary"],
            "size": limit,  # Use actual limit instead of initial_fetch_limit
            "from": offset,
        }

        if industry is not None:

            combined_query["query"]["bool"]["filter"].append(
                {"term": {"industry.keyword": industry}}
            )

        # Log query without vector fields
        log_query = remove_vector_fields(combined_query)
        # mcp_server_logger.debug(json.dumps(log_query, indent=2, ensure_ascii=False))

        # Execute the search
        response = client.search(body=combined_query, index=OPENSEARCH_DOCUMENT_INDEX)
        mcp_server_logger.info(
            f"opensearch response: {response}"
        )
        # Process results directly
        results = []
        for hit in response["hits"]["hits"]:
            doc = {key: hit["_source"].get(key) for key in DOCUMENT_SOURCE_FIELDS}
            results.append(doc)

        total_hits = response["hits"]["total"]["value"]

        if results:
            return {
                "results": results,
                "pagination": {
                    "total_hits": total_hits,
                    "current_offset": offset,
                    "limit": limit,
                    "has_more": total_hits > offset + limit,
                    "next_offset": (
                        offset + limit if total_hits > offset + limit else None
                    ),
                    "previous_offset": offset - limit if offset > 0 else None,
                },
            }

        else:
            # No results to rerank
            return {
                "results": [],
                "pagination": {
                    "total_hits": total_hits,
                    "current_offset": offset,
                    "limit": limit,
                    "has_more": total_hits > offset + limit,
                    "next_offset": (
                        offset + limit if total_hits > offset + limit else None
                    ),
                    "previous_offset": offset - limit if offset > 0 else None,
                },
            }

    except Exception as e:
        mcp_server_logger.error(f"Error searching documents: {str(e)}")
        tb_str = traceback.format_exc()
        mcp_server_logger.error(
            f"Error searching documents : Stack trace:\n{tb_str}")

        return {
            "results": [],
            "error": str(e),
            "search_metadata": {
                "query": query_text,
                "industry": industry,
            },
        }


# Separate function for reranking with Cohere Rerank 3.5
# async def rerank_with_cohere(query_text, documents, top_n=20, advanced_options=None):
#     """
#     Advanced reranking using Cohere Rerank 3.5 via direct Bedrock model invocation
#
#     Args:
#         query_text (str): The query to rerank documents against
#         documents (list): List of documents to rerank
#         top_n (int): Number of top results to return
#         advanced_options (dict): Optional advanced configuration
#
#     Returns:
#         list: Reranked documents with scores
#     """
#     # Initialize options with defaults
#     options = {
#         "model_id": "cohere.rerank-v3-5:0",
#         "return_documents": True,
#         "timeout": 30,
#         "max_retries": 3,
#     }
#
#     # Update with user-provided options
#     if advanced_options:
#         options.update(advanced_options)
#
#     # Set temporary logging level if specified
#
#     try:
#         # Validate inputs
#         if not documents:
#             mcp_server_logger.warning("No documents provided for reranking")
#             return []
#
#         if not query_text or not query_text.strip():
#             mcp_server_logger.warning("Empty query text provided for reranking")
#             return documents
#
#         # Initialize Bedrock runtime client
#         bedrock_client = boto3.client(
#             "bedrock-runtime",
#             region_name="us-west-2",
#         )
#
#         # Ensure we don't request more results than we have documents
#         effective_top_n = min(top_n, len(documents))
#
#         # Prepare the request body for Cohere Rerank
#         request_body = {
#             "query": query_text,
#             "documents": documents,
#             "top_n": effective_top_n,
#             "api_version": 2,
#         }
#
#         # Convert to JSON string for Bedrock
#         body_json = json.dumps(request_body)
#
#         mcp_server_logger.debug(
#             f"Sending rerank request with {len(documents)} documents"
#         )
#
#         # Make the async call to Bedrock
#         loop = asyncio.get_event_loop()
#         response = await loop.run_in_executor(
#             None,
#             lambda: bedrock_client.invoke_model(
#                 modelId=options["model_id"],
#                 contentType="application/json",
#                 accept="application/json",
#                 body=body_json,
#             ),
#         )
#
#         # Parse the response
#         reranked_results = json.loads(response["body"].read())["results"]
#
#         mcp_server_logger.info(
#             f"Successfully reranked {len(reranked_results)} documents"
#         )
#         return reranked_results
#
#     except Exception as e:
#         mcp_server_logger.error(f"Unexpected error during Cohere reranking: {str(e)}")
#
#         # Return original documents on error
#         return documents


async def get_text_embedding(
    text_content: str
) -> list[float]:
    """
    Generate text embeddings using Amazon Bedrock's Cohere multilingual embedding model.
    Returns:
        A list of floating point numbers representing the text embedding vector
    """
    EMBEDDING_MODEL_ID = os.environ.get("EMBEDDING_MODEL_ID")
    bedrock_runtime = boto3.client("bedrock-runtime")

    if "cohere" in EMBEDDING_MODEL_ID:
        request_body = {
            "texts": [text_content[:2048]],
            "input_type": "search_query",  # Optimized for search queries
            "truncate": "END",  # Truncate from the end if text exceeds model's max length
        }

        # Invoke the Bedrock model
        response = bedrock_runtime.invoke_model(
            modelId=EMBEDDING_MODEL_ID, body=json.dumps(request_body)
        )

        # Parse the response body
        response_body = json.loads(response["body"].read())

        # Extract the embedding vector (a list of floats)
        embedding = response_body["embeddings"][0]

        return embedding
    else:
        body = {"inputText": text_content}
        # invoke_bedrock
    response = bedrock_runtime.invoke_model(
        contentType="application/json",
        accept="*/*",
        modelId=EMBEDDING_MODEL_ID,
        body=json.dumps(body),
    )

    response_body = json.loads(response.get("body").read())

    return response_body["embedding"]



if __name__ == "__main__":
    # For local testing only - this uses stdio, not SSE
    mcp_server.run(stateless_http=True)
