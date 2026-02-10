"""
Lambda function that processes new files in S3:
1. Extracts content from S3 files
2. Generates embeddings using Bedrock
3. Performs content analysis
4. Stores results in OpenSearch database
"""

import json
import logging
import os
import re

import boto3
import datetime
from common.bedrock_embedding import get_embedding_from_text, get_bedrock_runtime_client
from common.db_secret import get_opensearch_client
from common.html_processor import clear_html_content
from common.json_utils import parse_json_markdown
from typing import Dict, List, Any, Union
import time
import json_repair

from prompt import url_prompt_matching, DEFAULT_PROMPT, EXTRACTION_PROMPT_FASHION
import traceback

# Import PDF processing utilities
from common.pdf_processor import extract_text_from_pdf_s3, extract_pdf_text_from_s3_url, is_pdf_processing_available

"""
Configure logging based on environment variables using default format.
Returns configured logger instance.
"""
# Get log level from environment variable, default to INFO if not set


# Get the numeric log level, default to INFO if invalid level specified
log_level = int(os.environ.get("LOG_LEVEL", logging.INFO))

# Get the root logger and set its level
logger = logging.getLogger("data-ingestion")
logger.setLevel(log_level)


def process_images(
    document_metadata: Dict[str, Any], main_content_html: str, base_url: str
) -> List[Dict[str, Any]]:
    """
    Process images from document metadata and main content HTML.

    This function:
    1. Extracts image URLs from main content HTML
    2. Normalizes image URLs for consistent comparison
    3. Removes duplicate images based on normalized URLs
    4. Marks images that appear in the main content

    Args:
        document_metadata (Dict): Document metadata containing image information
        main_content_html (str): HTML content of the main article
        base_url (str): Base URL for resolving relative image paths

    Returns:
        List[Dict]: Deduplicated list of image objects with in_main_content flag
    """

    # Function to normalize URLs for comparison
    def normalize_url(url: str, base: str = None) -> str:
        if not url:
            return ""

        # Handle data URLs
        if url.startswith("data:"):
            return url

        # Already absolute
        if url.startswith(("http://", "https://")):
            return url

        # No base URL available
        if not base:
            return url

        from urllib.parse import urlparse

        parsed = urlparse(base)

        # Protocol-relative URL
        if url.startswith("//"):
            return f"{parsed.scheme}:{url}"

        # Root-relative URL
        if url.startswith("/"):
            return f"{base}{url}"

        # Path-relative URL (simplified)
        return f"{base}/{url}"

    # Extract image URLs from main content HTML
    main_content_image_urls = set()
    if main_content_html:
        from bs4 import BeautifulSoup

        # Parse the HTML fragment
        soup = BeautifulSoup(main_content_html, "html.parser")

        # Extract all image URLs from mainContentHTML
        for img in soup.find_all("img"):
            src = img.get("src", "")
            absolute_src = normalize_url(src, base_url)
            main_content_image_urls.add(absolute_src)
            logger.debug(f"Found image in main content: {absolute_src}")
    else:
        logger.debug("No main content HTML provided")

    # Process document_metadata images - add in_main_content field and remove duplicates
    processed_images = []
    seen_urls = set()  # Track seen URLs to remove duplicates

    if document_metadata and "images" in document_metadata:
        for img_info in document_metadata["images"]:
            if "original_url" in img_info:
                # Normalize the original URL for comparison
                original_url_normalized = normalize_url(
                    img_info["original_url"], base_url
                )

                # Skip this image if we've already seen this URL
                if original_url_normalized in seen_urls:
                    logger.debug(f"Skipping duplicate image: {original_url_normalized}")
                    continue

                # Add to seen URLs
                seen_urls.add(original_url_normalized)

                # Set in_main_content flag based on URL matching
                img_info["in_main_content"] = (
                    original_url_normalized in main_content_image_urls
                )

                # Add to processed images
                processed_images.append(img_info)

                logger.debug(
                    f"Image {original_url_normalized} in main content: {img_info['in_main_content']}"
                )

    logger.debug(f"Total unique images processed: {len(processed_images)}")
    return processed_images


def convert_ms_timestamp(timestamp_ms: Union[int, str]) -> str:
    """
    Convert a millisecond timestamp to a formatted date-time string.

    Args:
        timestamp_ms (Union[int, str]): The timestamp in milliseconds. Can be either an integer
            or a string that can be converted to an integer.

    Returns:
        str: A formatted date-time string in ISO 8601 format (YYYY-MM-DD HH:MM:SS)

    Example:
        >>> convert_ms_timestamp(1609459200000)
        '2021-01-01 00:00:00'
        >>> convert_ms_timestamp("1609459200000")
        '2021-01-01 00:00:00'
    """
    # Ensure timestamp_ms is an integer
    if isinstance(timestamp_ms, str):
        timestamp_ms = int(timestamp_ms)

    # Convert milliseconds to seconds
    timestamp_s = timestamp_ms / 1000
    # Format as ISO 8601 string
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp_s))



def _generate_embedding_and_store(
    analysis_results: Dict[str, Any],
    s3_location: str,
    time_collected: str,
    original_url: str,
    file_type: str = "file"
) -> None:
    """
    Common function to generate embeddings and store results in database.
    
    Args:
        analysis_results (Dict[str, Any]): Analysis results from Bedrock
        s3_location (str): S3 location of the file
        time_collected (str): Timestamp when the content was collected
        original_url (str): Original URL of the content
        file_type (str): Type of file being processed (for logging)
    """
    # Generate embedding using Bedrock
    embedding = get_embedding_from_text(analysis_results["summary"])
    logger.debug(f"Generated embedding with length: {len(embedding)}")
    
    # Store results in database
    try:
        logger.debug(f"Start to store {file_type} data in opensearch serverless.")
        db_response = store_in_database(
            s3_location=s3_location,
            content_vector=embedding,
            time_collected=time_collected,
            original_url=original_url,
            document_data=analysis_results,
        )
        logger.info(
            f"Database storage result for {file_type}: {db_response['index_response']['result']}"
        )
    except Exception as e:
        tb_str = traceback.format_exc()
        logger.error(f"Failed to store {file_type} data in database: {str(e)}\nStack trace:\n{tb_str}")
        raise


def _process_text_file(s3_client: boto3.client, bucket: str, key: str) -> None:
    """
    Process a text-based file (.txt or .pdf) from S3.
    
    Args:
        s3_client: S3 client instance
        bucket: S3 bucket name
        key: S3 object key
    """
    # Determine file type and extraction method
    if key.endswith('.pdf'):
        file_type = "pdf"
        logger.info(f"Processing .pdf file: {key}")
        
        # Extract text content from PDF file
        try:
            text_content = extract_text_from_pdf_s3(s3_client, bucket, key)
            logger.debug(f"Extracted PDF text length: {len(text_content)} characters")
        except Exception as e:
            logger.error(f"Failed to extract text from PDF {key}: {str(e)}")
            # Create a fallback message for failed PDF extraction
            text_content = f"Failed to extract text from PDF file: {str(e)}"
    else:
        file_type = "txt"
        logger.info(f"Processing .txt file: {key}")
        
        # Extract content from .txt file
        text_content = extract_content_from_s3(s3_client, bucket, key)
        logger.debug(f"Extracted txt content length: {len(text_content)} characters")
    
    # Step 2: Analyze text content using the dedicated function
    # Use default prompt for text files
    prompt = DEFAULT_PROMPT
    logger.debug(f"Using default prompt for .{file_type} file processing")
    
    # Create original_url for text files (S3 location)
    original_url = f"s3://{bucket}/{key}"
    
    # Analyze the text content using the dedicated function
    analysis_results = analyze_txt_content(text_content, prompt, original_url)
    logger.debug(f"Analysis results for {file_type}: {json.dumps(analysis_results, default=str)}")
    
    # Step 3: Generate embedding and store in database
    s3_location = f"s3://{bucket}/{key}"
    time_collected = datetime.datetime.now().isoformat()
    
    _generate_embedding_and_store(
        analysis_results=analysis_results,
        s3_location=s3_location,
        time_collected=time_collected,
        original_url=original_url,
        file_type=file_type
    )


def _process_html_file(s3_client: boto3.client, bucket: str, key: str) -> None:
    """
    Process a metadata.json file and its corresponding HTML file from S3.
    
    Args:
        s3_client: S3 client instance
        bucket: S3 bucket name
        key: S3 object key (metadata.json)
    """
    logger.info(f"Processing metadata.json file: {key}")
    
    # Step 1: Extract content from S3 file as JSON
    metadata_text = extract_content_from_s3(s3_client, bucket, key)
    logger.debug(f"Extracted metadata text: {metadata_text[:200]}...")  # Log first 200 chars

    try:
        document_metadata = json.loads(metadata_text)
        logger.debug(
            f"Successfully parsed metadata JSON: {json.dumps(document_metadata, default=str)[:200]}..."
        )
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse metadata JSON: {str(e)}")
        logger.error(f"Raw metadata content (first 500 chars): {metadata_text[:500]}")
        raise

    # Step 2: Download articles from s3
    article_key = key.replace("metadata.json", "article.html")
    logger.debug(f"Fetching article from key: {article_key}")
    content_text = extract_content_from_s3(s3_client, bucket, article_key)
    logger.debug(f"Article {article_key} content length: {len(content_text)} characters")

    # Step 3: Analyze content
    # Get the appropriate prompt based on the original_url in document_metadata
    # Extract the base URL from the original_url to match with url_prompt_mapping keys
    original_url = document_metadata.get("original_url", "")

    # Use the default prompt from prompt.py in case no matching URL pattern is found
    prompt = DEFAULT_PROMPT  # Set default prompt initially

    # Find the matching prompt for the URL
    logger.info(f"Looking for prompt match for original_url: {original_url}")
    logger.info(f"Available URL patterns: {list(url_prompt_matching.keys())}")
    
    for url_pattern, url_prompt in url_prompt_matching.items():
        # Normalize both URLs by removing trailing slashes for comparison
        normalized_pattern = url_pattern.rstrip('/')
        normalized_url = original_url.rstrip('/') if original_url else ""
        
        logger.debug(f"Comparing normalized_url '{normalized_url}' with pattern '{normalized_pattern}'")
        
        if normalized_url and normalized_url.startswith(normalized_pattern):
            prompt = url_prompt
            logger.info(f"✅ MATCHED! Using prompt for URL pattern: {url_pattern}")
            logger.info(f"Prompt type: {'FASHION' if url_prompt == EXTRACTION_PROMPT_FASHION else 'OTHER'}")
            break

    if prompt == DEFAULT_PROMPT:
        logger.warning(
            f"❌ No specific prompt found for URL: {original_url}. Using default prompt."
        )

    # Pass the prompt, original_url, and document_metadata to the analyze_content function
    analysis_results = analyze_content(
        content_text, prompt, original_url, document_metadata, bucket, article_key
    )
    logger.debug(f"Analysis results: {json.dumps(analysis_results, default=str)}")

    # Step 4: Generate embedding and store in database
    s3_location = f"s3://{bucket}/{key.replace('metadata.json', 'article.html')}"

    from datetime import datetime

    # 原始时间字符串
    original_time = document_metadata.get("download_time") or document_metadata.get("timestamp")

    # 解析原始时间
    dt = datetime.fromisoformat(original_time)

    # 转换为OpenSearch格式（保留毫秒，3位小数）
    opensearch_format_time = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

    _generate_embedding_and_store(
        analysis_results=analysis_results,
        s3_location=s3_location,
        time_collected=opensearch_format_time,
        original_url=document_metadata["original_url"],
        file_type="html"
    )


def process_one_item(
    s3_client: boto3.client, s3_event: Dict[str, Any], message_received_time: str
) -> None:
    bucket = s3_event["s3"]["bucket"]["name"]
    key = s3_event["s3"]["object"]["key"]

    logger.debug(f"Processing item from bucket: {bucket}, key: {key}")

    # Check file type and delegate to appropriate processor
    if key.endswith('.txt') or key.endswith('.pdf'):
        _process_text_file(s3_client, bucket, key)
    else:
        _process_html_file(s3_client, bucket, key)


def extract_content_from_s3(s3_client: boto3.client, bucket: str, key: str) -> str:
    """
    Extract and return the content from an S3 file as a string.

    This function downloads a file from S3, decodes its content as UTF-8 text.
    It handles any exceptions that might occur during
    the download, decoding.

    Args:
        s3_client (boto3.client): Boto3 S3 client instance
        bucket (str): S3 bucket name containing the file
        key (str): S3 object key (path to the file within the bucket)

    Returns:
        str: The raw content of the file as a string

    Raises:
        Exception: If there's an error downloading or decoding the file
    """
    try:
        logger.debug(f"Attempting to download from S3: bucket={bucket}, key={key}")

        # Download the file from S3
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")

        content_length = len(content)
        logger.debug(
            f"Successfully downloaded content from S3, length: {content_length} characters"
        )

        # Check if content is empty
        if content_length == 0:
            logger.warning(
                f"Downloaded content is empty for bucket={bucket}, key={key}"
            )

        return content

    except Exception as e:
        logger.error(f"Error extracting content from S3: {str(e)}")
        logger.error(f"Failed S3 parameters: bucket={bucket}, key={key}")
        raise





def _call_bedrock_for_analysis(
    content: str,
    prompt: str = None,
    content_type_label: str = "content",
) -> Dict[str, Any]:
    """
    Common function to call Bedrock for content analysis.
    
    Args:
        content (str): The content to analyze
        prompt (str, optional): The prompt to use for analysis
        content_type_label (str): Label for the content type (for logging and user message)
    
    Returns:
        Dict[str, Any]: Raw analysis results from Bedrock
    """
    bedrock_client = get_bedrock_runtime_client()
    logger.debug(f"Analyzing {content_type_label} length: {len(content)} characters")
    
    # Use the provided prompt if available, otherwise use the default prompt
    system_prompt = (
        prompt
        if prompt
        else f"Extract key information from this {content_type_label} and return it as JSON."
    )

    # Create user message with appropriate label
    user_message = f"## {content_type_label.title()} \n" + content
    logger.debug(f"user_message: {user_message}")

    response = bedrock_client.converse(
        modelId=os.environ.get("EXTRACTION_MODEL"),
        messages=[{"role": "user", "content": [{"text": user_message}]}],
        system=[{"text": system_prompt}],
    )

    output_message = response["output"]["message"]
    logger.debug(f"Extracted content from Bedrock response: {output_message}")
    
    # Parse the JSON response from Bedrock and return it directly
    analysis_json = parse_json_markdown(output_message["content"][0]["text"])

    # Add default values for any missing fields to ensure consistency
    defaults = {"title": "Untitled", "summary": "", "keywords": []}
    logger.debug(f"{content_type_label} analysis_json: {json.dumps(analysis_json, indent=4)}")
    for key, value in defaults.items():
        if key not in analysis_json:
            analysis_json[key] = value

    return analysis_json


def analyze_txt_content(
    txt_content: str,
    prompt: str = None,
    original_url: str = None,
) -> Dict[str, Any]:
    """
    Analyze plain text content and extract insights.

    This function processes .txt files by sending the content directly to Bedrock
    for analysis without HTML processing or image handling.

    Args:
        txt_content (str): The plain text content to analyze
        prompt (str, optional): The prompt to use for analysis. Defaults to None.
        original_url (str, optional): The original URL/location of the content.

    Returns:
        Dict[str, Any]: Analysis results as returned by the Bedrock model
    """
    # Call the common Bedrock analysis function
    analysis_json = _call_bedrock_for_analysis(
        content=txt_content,
        prompt=prompt,
        content_type_label="text content"
    )

    # For txt files, no image processing needed
    analysis_json["images"] = []
    
    logger.debug(f"Bedrock txt analysis result: {json.dumps(analysis_json, indent=2)}")
    return analysis_json


def analyze_content(
    content: str,
    prompt: str = None,
    original_url: str = None,
    document_metadata: Dict = None,
    bucket: str = None,
    article_key: str = None,
) -> Dict[str, Any]:
    """
    Analyze the content and extract insights.

    This function uses the content text and sends it to Bedrock to extract
    meaningful information and insights. It also marks which images from document_metadata
    appear in the main content by comparing the original_url field.

    Args:
        content (str): The text content to analyze (HTML)
        prompt (str, optional): The prompt to use for analysis. Defaults to None.
        original_url (str, optional): The original URL of the content, used for resolving relative image paths.
        document_metadata (Dict, optional): The document metadata containing image information.
        bucket (str, optional): S3 bucket name for HTML processing.
        article_key (str, optional): S3 key for HTML processing.

    Returns:
        Dict[str, Any]: Analysis results as returned by the Bedrock model, plus image information
    """
    # Clean HTML content
    cleaned_content = clear_html_content(content, bucket, article_key)
    
    # Call the common Bedrock analysis function
    analysis_json = _call_bedrock_for_analysis(
        content=cleaned_content,
        prompt=prompt,
        content_type_label="webpage text content"
    )

    # Create a base URL from original_url if available
    base_url = None
    if original_url:
        try:
            from urllib.parse import urlparse

            parsed_url = urlparse(original_url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            logger.debug(f"Using base URL for images: {base_url}")
        except Exception as e:
            logger.warning(f"Failed to parse original_url for base URL: {str(e)}")

    # Process images from main content HTML and document metadata
    main_content_html = analysis_json.get("mainContentHTML", "")
    analysis_json["images"] = process_images(
        document_metadata, main_content_html, base_url
    )

    logger.debug(f"Bedrock analysis result: {json.dumps(analysis_json, indent=2)}")
    return analysis_json


def store_in_database(
    s3_location: str,
    content_vector: List[float],
    time_collected: str,
    original_url: str = None,
    document_data: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Store the processed data in OpenSearch.

    This function connects to OpenSearch and indexes the document data
    along with required metadata and vector embeddings.
    If a record with the same s3_location already exists, it will be updated
    instead of creating a duplicate.

    Args:
        s3_location (str): S3 location of the original file
        content_vector (List[float]): Vector embedding of the content
        time_collected (str): Timestamp when the content was collected
        original_url (str, optional): Original URL of the content. Defaults to None.
        document_data (Dict[str, Any], optional): All additional document fields. Defaults to empty dict.

    Returns:
        Dict[str, Any]: Response with indexing results

    Raises:
        Exception: If there's an error connecting to OpenSearch or executing the indexing
    """
    if document_data is None:
        document_data = {}

    try:
        client = get_opensearch_client()
        index_name = os.environ.get("OPENSEARCH_INDEX", "")

        if not index_name:
            logger.error("OPENSEARCH_INDEX environment variable not set")
            raise ValueError("OpenSearch index name not configured")

        if not content_vector or not isinstance(content_vector, list):
            logger.error("Invalid content_vector format")
            raise ValueError("Content vector must be a non-empty list")

        # Prepare document for indexing with required fields
        document = {
            "s3_location": s3_location,
            "content_vector": content_vector,
            "time_collected": time_collected,
        }

        # Add original_url if provided
        if original_url:
            document["original_url"] = original_url
        logger.debug("Before update document data")
        # Add all additional fields from document_data
        document.update(document_data)
        logger.debug("After update document data")

        # Log document being indexed (without the vector for brevity)
        log_doc = {k: v for k, v in document.items() if k != "content_vector"}
        logger.debug(f"Indexing document: {json.dumps(log_doc)}")

        # Check if a document with the same s3_location already exists
        search_response = client.search(
            index=index_name,
            body={"query": {"term": {"s3_location.keyword": s3_location}}, "size": 1},
        )

        # If document exists, update it instead of creating a new one
        if search_response["hits"]["total"]["value"] > 0:
            existing_doc_id = search_response["hits"]["hits"][0]["_id"]
            logger.info(
                f"Found existing document with ID: {existing_doc_id} for s3_location: {s3_location}"
            )

            # Add time_updated timestamp for updates
            document["time_updated"] = datetime.datetime.now().isoformat()

            # Update the existing document
            response = client.update(
                index=index_name, id=existing_doc_id, body={"doc": document}
            )

            logger.info(f"Updated existing document with ID: {existing_doc_id}")

        else:
            # No existing document found, create a new one
            # Add time_created for new documents only
            document["time_created"] = datetime.datetime.now().isoformat()
            document["time_updated"] = datetime.datetime.now().isoformat()

            response = client.index(index=index_name, body=document)
            logger.info(f"Created new document with ID: {response['_id']}")

        return {
            "index_response": {
                "result": response["result"],
                "index": response["_index"],
                "id": response["_id"],
                "status": response["result"] in ["created", "updated"],
            }
        }

    except Exception as e:
        logger.error(f"Error storing data in OpenSearch: {str(e)}")
        raise





def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler that processes S3 events for new files.

    The function:
    1. Extracts the file content from S3
    2. Generates embeddings using Bedrock
    3. Analyzes the content
    4. Stores results in OpenSearch database

    Args:
        event (Dict[str, Any]): The event dict from AWS Lambda containing S3 event information
        context (Any): The context object from AWS Lambda

    Returns:
        Dict[str, Any]: Response with status code and processing results
    """
    # Debug log the incoming event
    logger.debug(f"Received event: {json.dumps(event, default=str)}")

    # Initialize AWS clients
    s3 = boto3.client("s3")
    total = 0
    success = 0
    try:
        # Process each record in the event
        for record in event.get("Records", []):
            # Handle SQS event containing S3 notification
            if record.get("eventSource") == "aws:sqs":
                try:
                    # Parse the SQS message body which contains the S3 event
                    sqs_body = json.loads(record.get("body"))

                    # Check if this is a direct S3 event or wrapped in 'Records'
                    if "Records" in sqs_body:
                        for s3_event in sqs_body["Records"]:
                            total += 1
                            try:
                                process_one_item(
                                    s3,
                                    s3_event,
                                    record.get("attributes").get(
                                        "ApproximateFirstReceiveTimestamp"
                                    ),
                                )
                                success += 1
                            except Exception as e:
                                tb_str = traceback.format_exc()
                                logger.error(f"Error processing one item: {str(e)}\nStack trace:\n{tb_str}")
                                continue

                    else:
                        s3_event = sqs_body
                        total += 1
                        try:
                            process_one_item(
                                s3,
                                s3_event,
                                record.get("attributes").get("SentTimestamp"),
                            )
                            success += 1
                        except Exception as e:
                            tb_str = traceback.format_exc()
                            logger.error(f"Error processing one item: {str(e)}\nStack trace:\n{tb_str}")
                            continue

                except Exception as e:
                    logger.error(f"Error parsing SQS message: {str(e)}")
                    logger.error(f"Raw SQS message body: {record.get('body')}")
                    continue  # Skip this record and process the next one

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Processing completed",
                    "total": total,
                    "success": success,
                    "failed": total - success,
                }
            ),
        }

    except Exception as e:
        logger.critical(f"Error processing event: {str(e)}")
        return {"statusCode": 500, "body": json.dumps(f"Error: {str(e)}")}

