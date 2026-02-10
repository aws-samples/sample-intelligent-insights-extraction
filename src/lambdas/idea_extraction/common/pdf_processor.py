"""
PDF processing utilities for extracting text content from PDF files.

This module provides functions to extract text from PDF files stored in S3
using multiple PDF processing libraries (PyPDF2 and pdfplumber) for better reliability.
"""

import io
import re
import logging
import boto3
from typing import Dict, Any

# PDF processing imports
try:
    import PyPDF2
    import pdfplumber
    PDF_LIBRARIES_AVAILABLE = True
except ImportError:
    logging.getLogger("data-ingestion").warning("PDF processing libraries not available. PDF processing will be disabled.")
    PDF_LIBRARIES_AVAILABLE = False

logger = logging.getLogger("data-ingestion")


def extract_text_from_pdf_s3(s3_client: boto3.client, bucket: str, key: str) -> str:
    """
    Extract text content from a PDF file stored in S3.
    
    This function downloads a PDF from S3, extracts all text content using multiple
    PDF processing libraries for better reliability, and returns the combined text.
    
    Args:
        s3_client (boto3.client): Boto3 S3 client instance
        bucket (str): S3 bucket name containing the PDF file
        key (str): S3 object key (path to the PDF file within the bucket)
    
    Returns:
        str: Extracted text content from the PDF
        
    Raises:
        Exception: If PDF libraries are not available or extraction fails
    """
    if not PDF_LIBRARIES_AVAILABLE:
        raise Exception("PDF processing libraries (PyPDF2, pdfplumber) are not available")
    
    try:
        logger.debug(f"Attempting to download PDF from S3: bucket={bucket}, key={key}")
        
        # Download the PDF file from S3
        response = s3_client.get_object(Bucket=bucket, Key=key)
        pdf_content = response["Body"].read()
        
        logger.debug(f"Successfully downloaded PDF from S3, size: {len(pdf_content)} bytes")
        
        # Extract text using multiple methods for better reliability
        extracted_text = ""
        
        # Method 1: Try pdfplumber first (generally better for complex layouts)
        try:
            with io.BytesIO(pdf_content) as pdf_buffer:
                import pdfplumber
                with pdfplumber.open(pdf_buffer) as pdf:
                    text_parts = []
                    for page_num, page in enumerate(pdf.pages, 1):
                        try:
                            page_text = page.extract_text()
                            if page_text:
                                text_parts.append(f"--- Page {page_num} ---\n{page_text}\n")
                                logger.debug(f"Extracted {len(page_text)} characters from page {page_num}")
                        except Exception as e:
                            logger.warning(f"Failed to extract text from page {page_num} using pdfplumber: {str(e)}")
                    
                    if text_parts:
                        extracted_text = "\n".join(text_parts)
                        logger.info(f"Successfully extracted {len(extracted_text)} characters using pdfplumber")
        
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {str(e)}")
        
        # Method 2: Fallback to PyPDF2 if pdfplumber fails or extracts nothing
        if not extracted_text.strip():
            try:
                with io.BytesIO(pdf_content) as pdf_buffer:
                    import PyPDF2
                    pdf_reader = PyPDF2.PdfReader(pdf_buffer)
                    text_parts = []
                    
                    for page_num, page in enumerate(pdf_reader.pages, 1):
                        try:
                            page_text = page.extract_text()
                            if page_text:
                                text_parts.append(f"--- Page {page_num} ---\n{page_text}\n")
                                logger.debug(f"Extracted {len(page_text)} characters from page {page_num}")
                        except Exception as e:
                            logger.warning(f"Failed to extract text from page {page_num} using PyPDF2: {str(e)}")
                    
                    if text_parts:
                        extracted_text = "\n".join(text_parts)
                        logger.info(f"Successfully extracted {len(extracted_text)} characters using PyPDF2")
            
            except Exception as e:
                logger.warning(f"PyPDF2 extraction failed: {str(e)}")
        
        # Clean up the extracted text
        if extracted_text:
            # Remove excessive whitespace and normalize line breaks
            extracted_text = re.sub(r'\n\s*\n\s*\n', '\n\n', extracted_text)  # Remove excessive line breaks
            extracted_text = re.sub(r'[ \t]+', ' ', extracted_text)  # Normalize spaces and tabs
            extracted_text = extracted_text.strip()
            
            logger.info(f"Final extracted text length: {len(extracted_text)} characters")
            return extracted_text
        else:
            logger.warning("No text could be extracted from the PDF")
            return "No text content could be extracted from this PDF file."
    
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        logger.error(f"Failed PDF parameters: bucket={bucket}, key={key}")
        raise


def extract_pdf_text_from_s3_url(s3_url: str) -> str:
    """
    Standalone function to extract text from a PDF file given its S3 URL.
    
    This function can be called independently to extract text from any PDF
    stored in S3, given its full S3 URL (e.g., s3://bucket-name/path/to/file.pdf).
    
    Args:
        s3_url (str): Full S3 URL of the PDF file (e.g., "s3://my-bucket/documents/file.pdf")
    
    Returns:
        str: Extracted text content from the PDF
        
    Raises:
        ValueError: If the S3 URL format is invalid
        Exception: If PDF extraction fails
        
    Example:
        text = extract_pdf_text_from_s3_url("s3://my-bucket/documents/report.pdf")
    """
    try:
        # Parse S3 URL
        if not s3_url.startswith('s3://'):
            raise ValueError(f"Invalid S3 URL format. Expected 's3://bucket/key', got: {s3_url}")
        
        # Remove 's3://' prefix and split bucket and key
        s3_path = s3_url[5:]  # Remove 's3://'
        if '/' not in s3_path:
            raise ValueError(f"Invalid S3 URL format. Missing key part: {s3_url}")
        
        bucket, key = s3_path.split('/', 1)
        
        if not bucket or not key:
            raise ValueError(f"Invalid S3 URL format. Empty bucket or key: {s3_url}")
        
        logger.info(f"Extracting text from PDF: bucket={bucket}, key={key}")
        
        # Initialize S3 client
        s3_client = boto3.client("s3")
        
        # Extract text from PDF
        extracted_text = extract_text_from_pdf_s3(s3_client, bucket, key)
        
        logger.info(f"Successfully extracted {len(extracted_text)} characters from PDF: {s3_url}")
        return extracted_text
        
    except Exception as e:
        logger.error(f"Failed to extract text from PDF {s3_url}: {str(e)}")
        raise


def is_pdf_processing_available() -> bool:
    """
    Check if PDF processing libraries are available.
    
    Returns:
        bool: True if PDF processing libraries are available, False otherwise
    """
    return PDF_LIBRARIES_AVAILABLE