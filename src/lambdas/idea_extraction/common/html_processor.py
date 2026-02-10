"""
HTML Processing Utilities

This module contains utilities for cleaning and processing HTML content,
specifically optimized for handling large files with obfuscated JavaScript.
"""

import json
import logging
import os
import re
import html2text
import traceback
import boto3

# Configure logger - use the same logger name as handler.py for consistency
logger = logging.getLogger("data-ingestion")


def html_to_text(html_content: str) -> str:
    h = html2text.HTML2Text()
    h.ignore_links = True  # Do not convert links
    h.ignore_images = True  # Do not convert images

    # Convert HTML to markdown
    markdown_text = h.handle(html_content)

    # Remove all '*' and '#' characters
    text_no_md_marks = re.sub(r'[\*\#]+', '', markdown_text)

    # Replace multiple spaces or tabs with a single space
    text_single_space = re.sub(r'[ \t]+', ' ', text_no_md_marks)

    # Split text into lines
    lines = text_single_space.splitlines()

    # Remove lines that are empty or contain only whitespace
    non_empty_lines = [line.strip() for line in lines if line.strip() != '']

    # Join the lines back together with newline characters
    cleaned_text = '\n'.join(non_empty_lines)
    logger.debug(f"html_to_text cleaned_text: {cleaned_text}")

    return cleaned_text


def clear_html_content(html: str, bucket: str, article_key: str) -> str:
    """
    Convert HTML content to clean text with fallback logic:
    1. If HTML content is larger than ~1MB or Lambda processing fails, use html_to_text
    2. Otherwise, try to use Lambda function for HTML processing

    Args:
        html (str): The raw HTML content.
        bucket (str): S3 bucket name for Lambda processing.
        article_key (str): S3 key for the article.

    Returns:
        str: Cleaned text extracted from HTML.
    """

    # Check if HTML content is larger than ~1MB (1,048,576 bytes)
    html_size = len(html.encode('utf-8'))
    size_threshold = 1 * 1024 * 1024  # 1MB
    
    if html_size > size_threshold:
        logger.info(f"HTML content is large ({html_size} bytes > {size_threshold} bytes), using html_to_text fallback")
        try:
            return html_to_text(html)
        except Exception as e:
            tb_str = traceback.format_exc()
            logger.error(f"Error in html_to_text fallback for large content: {tb_str}")
            return ""
    
    # Try Lambda function processing for smaller content
    try:
        logger.info(f"HTML content size ({html_size} bytes) is within threshold, attempting Lambda processing")
        
        # Initialize Lambda client and use existing S3 bucket and key
        lambda_client = boto3.client("lambda")
        payload = {"s3_bucket": bucket, "s3_key": article_key}
        
        # Invoke the html_readability Lambda function
        logger.debug(f"Invoking html_readability Lambda function with bucket={bucket}, key={article_key}")
        response = lambda_client.invoke(
            FunctionName=os.environ.get(
                "HTML_READABILITY_FUNCTION_NAME", "html-readability-lambda"
            ),
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )
        
        # Parse the response
        response_payload = json.loads(response["Payload"].read().decode("utf-8"))
        response_body = json.loads(response_payload.get("body", "{}"))
        
        if response_payload.get("statusCode") == 200 and "content" in response_body:
            # Extract the processed content from the response
            processed_content = response_body["content"]
            logger.info(f"Lambda processing successful. Final length: {len(processed_content)}")
            if len(processed_content) < 10:
                raise Exception(f"Lambda processing failed, processed_content length less than 10, maybe like <p></p>")
            return processed_content
        else:
            error_msg = response_body.get('message', 'Unknown error')
            logger.warning(f"Lambda processing failed: {error_msg}")
            raise Exception(f"Lambda processing failed: {error_msg}")
            
    except Exception as e:
        tb_str = traceback.format_exc()
        logger.warning(f"Lambda processing failed, falling back to html_to_text: {tb_str}")
        
        # Fallback to html_to_text
        try:
            return html_to_text(html)
        except Exception as fallback_error:
            tb_str = traceback.format_exc()
            logger.error(f"Error in html_to_text fallback: {tb_str}")
            return ""


# def clear_html_content(html: str, bucket: str, article_key: str) -> str:
#     """
#     Clean HTML content using a hybrid approach:
#     1. First use optimized cleaning to remove obfuscated content
#     2. Optionally use Readability for semantic extraction on smaller, clean content
#
#     Args:
#         html (str): The raw HTML content to clean
#         bucket (str): S3 bucket name
#         article_key (str): S3 key for the article
#
#     Returns:
#         str: The cleaned HTML content
#     """
#     import boto3
#
#     content = html
#     use_readability = False
#
#     # Step 1: Always do initial cleaning to handle large/obfuscated content
#     try:
#         logger.info(f"Starting HTML cleaning. Original size: {len(html)} characters")
#
#         # Use our optimized cleaning first
#         cleaned_content = clean_html_for_llm(html)
#         logger.info(f"After initial cleaning: {len(cleaned_content)} characters")
#
#         # Decide whether to use Readability based on cleaned content size and quality
#         if len(cleaned_content) < 500000:  # 500KB threshold for Readability
#             # Check if the content looks like it has meaningful structure
#             if _has_meaningful_structure(cleaned_content):
#                 use_readability = True
#                 logger.info("Content is suitable for Readability processing")
#             else:
#                 logger.info("Content lacks meaningful structure, skipping Readability")
#         else:
#             logger.info("Content too large for Readability processing")
#
#         content = cleaned_content
#
#     except Exception as e:
#         logger.error(f"Error in initial HTML cleaning: {str(e)}")
#         # Continue with original content if cleaning fails
#         pass
#
#     # Step 2: Optionally use Readability for semantic extraction
#     if use_readability:
#         try:
#             # Save cleaned content to S3 temporarily for Readability processing
#             temp_key = f"temp/{article_key}_cleaned"
#             s3_client = boto3.client('s3')
#             s3_client.put_object(
#                 Bucket=bucket,
#                 Key=temp_key,
#                 Body=content.encode('utf-8'),
#                 ContentType='text/html'
#             )
#
#             # Initialize Lambda client
#             lambda_client = boto3.client("lambda")
#             payload = {"s3_bucket": bucket, "s3_key": temp_key}
#
#             # Invoke the html_readability Lambda function
#             logger.debug("Invoking html_readability Lambda function on cleaned content")
#             response = lambda_client.invoke(
#                 FunctionName=os.environ.get(
#                     "HTML_READABILITY_FUNCTION_NAME", "html-readability-lambda"
#                 ),
#                 InvocationType="RequestResponse",
#                 Payload=json.dumps(payload),
#             )
#
#             # Parse the response
#             response_payload = json.loads(response["Payload"].read().decode("utf-8"))
#             response_body = json.loads(response_payload.get("body", "{}"))
#
#             if response_payload.get("statusCode") == 200 and "content" in response_body:
#                 # Extract the semantically cleaned content from the response
#                 readability_content = response_body["content"]
#                 logger.info(
#                     f"Readability processing successful. Final length: {len(readability_content)}"
#                 )
#                 content = readability_content
#             else:
#                 logger.warning(
#                     f"Readability processing failed: {response_body.get('message', 'Unknown error')}"
#                 )
#                 # Keep our cleaned content
#
#             # Clean up temporary file
#             try:
#                 s3_client.delete_object(Bucket=bucket, Key=temp_key)
#             except:
#                 pass  # Ignore cleanup errors
#
#         except Exception as e:
#             logger.warning(
#                 f"Error in Readability processing: {str(e)}. Using optimized cleaning result."
#             )
#
#     # Final cleanup to ensure content is ready for LLM
#     try:
#         if len(content) > 100000:  # 100KB final limit for LLM processing
#             logger.warning(f"Final content still large ({len(content)} chars), truncating")
#             content = content[:100000] + "... [content truncated for LLM processing]"
#
#         logger.info(f"Final cleaned content: {len(content)} characters")
#         return content
#
#     except Exception as final_error:
#         logger.error(f"Error in final processing: {str(final_error)}")
#         return content[:10000] if content else ""  # Return first 10KB as last resort
#
#
# def clean_html_for_llm(html_content: str) -> str:
#     """
#     Clean HTML content by removing script, link, style tags and other elements
#     that are not useful for LLM processing to reduce token count.
#
#     Args:
#         html_content (str): Raw HTML content
#
#     Returns:
#         str: Cleaned HTML content
#     """
#     try:
#         if not html_content:
#             logger.debug("HTML content is empty or None")
#             return html_content or ""
#
#         if not isinstance(html_content, str):
#             logger.warning(f"HTML content is not a string: {type(html_content)}")
#             html_content = str(html_content)
#
#         # For very large content (>10MB), use optimized cleaning
#         if len(html_content) > 10 * 1024 * 1024:  # 10MB threshold
#             logger.warning(f"HTML content is very large ({len(html_content)} chars), using optimized cleaning")
#             return _clean_large_obfuscated_html(html_content)
#
#         # Check content length and use simple cleanup for large content
#         if len(html_content) > 1 * 1024 * 1024:  # 1MB threshold for regex operations
#             logger.warning(f"HTML content is large ({len(html_content)} chars), using simple cleanup")
#             return _simple_html_cleanup(html_content)
#
#         logger.debug(f"Starting HTML cleanup. Original length: {len(html_content)}")
#
#         # Remove script tags and their content
#         try:
#             html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
#         except Exception as e:
#             logger.warning(f"Error removing script tags: {e}")
#
#         # Remove style tags and their content
#         try:
#             html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
#         except Exception as e:
#             logger.warning(f"Error removing style tags: {e}")
#
#         # Remove link tags (self-closing and regular)
#         try:
#             html_content = re.sub(r'<link[^>]*/?>', '', html_content, flags=re.IGNORECASE)
#         except Exception as e:
#             logger.warning(f"Error removing link tags: {e}")
#
#         # Remove meta tags
#         try:
#             html_content = re.sub(r'<meta[^>]*/?>', '', html_content, flags=re.IGNORECASE)
#         except Exception as e:
#             logger.warning(f"Error removing meta tags: {e}")
#
#         # Remove comment blocks
#         try:
#             html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
#         except Exception as e:
#             logger.warning(f"Error removing comments: {e}")
#
#         # Remove noscript tags and their content
#         try:
#             html_content = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
#         except Exception as e:
#             logger.warning(f"Error removing noscript tags: {e}")
#
#         # Remove src attributes (images, videos, iframes, etc.)
#         try:
#             html_content = re.sub(r'\s+src\s*=\s*["\'][^"\']*["\']', '', html_content, flags=re.IGNORECASE)
#         except Exception as e:
#             logger.warning(f"Error removing src attributes: {e}")
#
#         # Remove other common attributes that consume tokens but aren't useful for content analysis
#         try:
#             html_content = re.sub(r'\s+href\s*=\s*["\'][^"\']*["\']', '', html_content, flags=re.IGNORECASE)
#             html_content = re.sub(r'\s+data-[^=]*\s*=\s*["\'][^"\']*["\']', '', html_content, flags=re.IGNORECASE)
#             html_content = re.sub(r'\s+class\s*=\s*["\'][^"\']*["\']', '', html_content, flags=re.IGNORECASE)
#             html_content = re.sub(r'\s+id\s*=\s*["\'][^"\']*["\']', '', html_content, flags=re.IGNORECASE)
#             html_content = re.sub(r'\s+style\s*=\s*["\'][^"\']*["\']', '', html_content, flags=re.IGNORECASE)
#             html_content = re.sub(r'\s+onclick\s*=\s*["\'][^"\']*["\']', '', html_content, flags=re.IGNORECASE)
#             html_content = re.sub(r'\s+onload\s*=\s*["\'][^"\']*["\']', '', html_content, flags=re.IGNORECASE)
#         except Exception as e:
#             logger.warning(f"Error removing attributes: {e}")
#
#         # Remove excessive whitespace and newlines
#         try:
#             html_content = re.sub(r'\s+', ' ', html_content)
#             html_content = re.sub(r'\n\s*\n', '\n', html_content)
#         except Exception as e:
#             logger.warning(f"Error cleaning whitespace: {e}")
#
#         result = html_content.strip()
#         logger.debug(f"HTML cleanup completed. Final length: {len(result)}")
#         return result
#
#     except Exception as e:
#         logger.error(f"Critical error in clean_html_for_llm: {str(e)}")
#         logger.error(f"Input type: {type(html_content)}, Input length: {len(html_content) if html_content else 'None'}")
#         # Use simple cleanup as fallback
#         logger.warning("Falling back to simple HTML cleanup")
#         return _simple_html_cleanup(html_content)
#
#
# def _clean_large_obfuscated_html(html_content: str) -> str:
#     """
#     Optimized cleaning for large HTML files with obfuscated JavaScript
#     Uses string operations instead of regex to avoid catastrophic backtracking
#     """
#     try:
#         logger.info(f"Processing large HTML content: {len(html_content)} characters")
#
#         # Step 1: Quick size check and truncation if necessary
#         if len(html_content) > 50 * 1024 * 1024:  # 50MB limit
#             logger.warning("HTML content exceeds 50MB, truncating to first 10MB")
#             html_content = html_content[:10 * 1024 * 1024]
#
#         # Step 2: Remove large blocks of obfuscated JavaScript using string operations
#         # Look for patterns that indicate obfuscated code blocks
#         lines = html_content.split('\n')
#         cleaned_lines = []
#         skip_block = False
#         obfuscated_patterns = ['li=', 'Ai?', 'case ', 'break;', '!function()', 'switch(']
#
#         for line in lines:
#             # Check if this line contains obfuscated JavaScript patterns
#             obfuscated_score = sum(1 for pattern in obfuscated_patterns if pattern in line)
#
#             # If line has multiple obfuscation patterns, skip it
#             if obfuscated_score >= 3:
#                 continue
#
#             # Skip very long lines that are likely obfuscated
#             if len(line) > 1000:
#                 continue
#
#             # Keep lines that look like actual HTML content
#             if any(tag in line.lower() for tag in ['<p', '<div', '<span', '<h1', '<h2', '<h3', '<article', '<section']):
#                 cleaned_lines.append(line)
#             elif len(line.strip()) < 200 and not any(pattern in line for pattern in obfuscated_patterns):
#                 cleaned_lines.append(line)
#
#         html_content = '\n'.join(cleaned_lines)
#         logger.info(f"After line-by-line filtering: {len(html_content)} characters")
#
#         # Step 3: Remove script and style blocks using simple string operations
#         html_content = _remove_blocks_simple(html_content, '<script', '</script>')
#         html_content = _remove_blocks_simple(html_content, '<style', '</style>')
#         html_content = _remove_blocks_simple(html_content, '<!--', '-->')
#
#         # Step 4: Simple attribute removal using string replacement
#         html_content = _remove_attributes_simple(html_content)
#
#         # Step 5: Clean up whitespace
#         html_content = ' '.join(html_content.split())
#
#         logger.info(f"Final cleaned content: {len(html_content)} characters")
#         return html_content
#
#     except Exception as e:
#         logger.error(f"Error in large HTML cleaning: {e}")
#         # Return a minimal version if all else fails
#         return html_content[:5000] if html_content else ""
#
#
# def _remove_blocks_simple(content: str, start_tag: str, end_tag: str) -> str:
#     """
#     Remove blocks between start and end tags using simple string operations
#     More efficient than regex for large content
#     """
#     try:
#         result = []
#         i = 0
#         while i < len(content):
#             start_pos = content.find(start_tag, i)
#             if start_pos == -1:
#                 result.append(content[i:])
#                 break
#
#             # Add content before the tag
#             result.append(content[i:start_pos])
#
#             # Find the end tag
#             end_pos = content.find(end_tag, start_pos)
#             if end_pos == -1:
#                 # No closing tag found, skip the rest
#                 break
#
#             # Skip to after the end tag
#             i = end_pos + len(end_tag)
#
#         return ''.join(result)
#     except Exception as e:
#         logger.warning(f"Error removing {start_tag} blocks: {e}")
#         return content
#
#
# def _remove_attributes_simple(content: str) -> str:
#     """
#     Remove common attributes using simple string operations
#     """
#     try:
#         # Remove common attributes that consume tokens
#         attributes_to_remove = [
#             'style=', 'class=', 'id=', 'data-', 'onclick=',
#             'onload=', 'href=', 'src=', 'alt='
#         ]
#
#         for attr in attributes_to_remove:
#             # Simple removal - find attribute and remove until next space or >
#             i = 0
#             while i < len(content):
#                 pos = content.find(attr, i)
#                 if pos == -1:
#                     break
#
#                 # Find the end of the attribute value
#                 quote_char = None
#                 start_pos = pos
#                 j = pos + len(attr)
#
#                 # Skip whitespace
#                 while j < len(content) and content[j] in ' \t\n':
#                     j += 1
#
#                 # Check for quote
#                 if j < len(content) and content[j] in '"\'':
#                     quote_char = content[j]
#                     j += 1
#                     # Find closing quote
#                     while j < len(content) and content[j] != quote_char:
#                         j += 1
#                     if j < len(content):
#                         j += 1  # Include closing quote
#                 else:
#                     # No quote, find next space or >
#                     while j < len(content) and content[j] not in ' \t\n>':
#                         j += 1
#
#                 # Remove the attribute
#                 content = content[:start_pos] + content[j:]
#                 i = start_pos
#
#         return content
#     except Exception as e:
#         logger.warning(f"Error removing attributes: {e}")
#         return content
#
#
# def _simple_html_cleanup(html_content: str) -> str:
#     """
#     Simple HTML cleanup as fallback when regex operations fail
#     """
#     try:
#         if not html_content:
#             return ""
#
#         # For very large content, use the optimized cleaner
#         if len(html_content) > 5 * 1024 * 1024:  # 5MB threshold
#             return _clean_large_obfuscated_html(html_content)
#
#         # Simple string replacements instead of regex
#         html_content = html_content.replace('<script', '<!--script')
#         html_content = html_content.replace('</script>', '</script-->')
#         html_content = html_content.replace('<style', '<!--style')
#         html_content = html_content.replace('</style>', '</style-->')
#
#         # Limit content length to prevent memory issues
#         if len(html_content) > 50000:  # 50KB limit
#             html_content = html_content[:50000] + "... [content truncated]"
#
#         return html_content.strip()
#     except Exception as e:
#         logger.error(f"Even simple cleanup failed: {e}")
#         return html_content[:1000] if html_content else ""  # Return first 1KB as last resort
#
#
# def _has_meaningful_structure(html_content: str) -> bool:
#     """
#     Check if HTML content has meaningful structure worth processing with Readability
#     """
#     try:
#         if not html_content or len(html_content) < 1000:
#             return False
#
#         # Count meaningful HTML tags
#         meaningful_tags = ['<p', '<div', '<article', '<section', '<h1', '<h2', '<h3', '<span']
#         tag_count = sum(html_content.lower().count(tag) for tag in meaningful_tags)
#
#         # Check for text content vs markup ratio
#         text_content = html_content
#         for tag in ['<script', '<style', '<link', '<meta']:
#             text_content = text_content.replace(tag, '')
#
#         # Remove all HTML tags to get approximate text content
#         text_only = re.sub(r'<[^>]+>', '', text_content)
#         text_ratio = len(text_only) / len(html_content) if html_content else 0
#
#         # Consider it meaningful if:
#         # 1. Has reasonable number of structural tags
#         # 2. Has good text-to-markup ratio
#         # 3. Not too much obfuscated content
#         obfuscated_patterns = ['li=', 'Ai?', 'case ', 'break;']
#         obfuscated_count = sum(html_content.count(pattern) for pattern in obfuscated_patterns)
#
#         is_meaningful = (
#             tag_count > 10 and  # Has structural elements
#             text_ratio > 0.1 and  # At least 10% actual text
#             obfuscated_count < 100  # Not heavily obfuscated
#         )
#
#         logger.debug(f"Structure analysis: tags={tag_count}, text_ratio={text_ratio:.2f}, obfuscated={obfuscated_count}, meaningful={is_meaningful}")
#         return is_meaningful
#
#     except Exception as e:
#         logger.warning(f"Error checking content structure: {e}")
#         return False
