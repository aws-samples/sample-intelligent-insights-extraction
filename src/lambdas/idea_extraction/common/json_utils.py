"""
JSON Processing Utilities

This module contains utilities for parsing and processing JSON content,
particularly for handling AI model responses that may contain JSON within
markdown formatting or mixed content.
"""

import json
import logging
import re
from typing import Dict, Any
import json_repair

# Configure logger
logger = logging.getLogger(__name__)


def parse_json_markdown(json_string: str) -> dict:
    """
    Extract and parse JSON content from a string that may contain markdown formatting.

    This function handles various formats that AI models might return JSON in:
    1. JSON within markdown code blocks (```json ... ```)
    2. Plain JSON without markdown formatting
    3. Mixed content with JSON at the end

    The function extracts the JSON content, cleans it, and parses it into a Python dictionary.

    Args:
        json_string (str): A string containing JSON content, possibly within markdown formatting

    Returns:
        dict: The parsed JSON content as a Python dictionary

    Raises:
        json.JSONDecodeError: If the extracted content cannot be parsed as valid JSON

    """
    logger.debug(f"Parsing JSON from string of length: {len(json_string)}")
    
    # Try to find JSON string within first and last triple backticks
    match = re.search(
        r"""```       # match first occuring triple backticks
                          (?:json)? # zero or one match of string json in non-capturing group
                          (.*)```   # greedy match to last triple backticks""",
        json_string,
        flags=re.DOTALL | re.VERBOSE,
    )

    json_str = None
    
    # If match found, use the content within the backticks
    if match is not None:
        json_str = match.group(1).strip()
        logger.debug("Found JSON within markdown code blocks")
    else:
        # Try to find JSON object at the end of the string
        # Look for the last occurrence of { that starts a complete JSON object
        brace_positions = []
        for i, char in enumerate(json_string):
            if char == '{':
                brace_positions.append(i)
        
        # Try each potential JSON start position from the end
        for start_pos in reversed(brace_positions):
            potential_json = json_string[start_pos:].strip()
            try:
                # Test if this is valid JSON
                test_parse = json.loads(potential_json, strict=False)
                if isinstance(test_parse, dict):  # Ensure it's a dictionary
                    json_str = potential_json
                    logger.debug(f"Found JSON object starting at position {start_pos}")
                    break
            except:
                continue
        
        # If no JSON object found, try the entire string
        if json_str is None:
            json_str = json_string.strip()
            logger.debug("Using entire string as JSON")

    # Strip whitespace and newlines from the start and end
    json_str = json_str.strip()
    # Replace non-breaking space with regular space
    json_str = json_str.replace("\xa0", " ")

    # Parse the JSON string into a Python dictionary
    try:
        parsed = json.loads(json_str, strict=False)
        logger.debug(f"Successfully parsed JSON, type: {type(parsed)}")
        
        # Ensure we return a dictionary
        if isinstance(parsed, dict):
            return parsed
        elif isinstance(parsed, list) and len(parsed) > 0:
            # If it's a list, try to find the first dictionary in it
            for item in parsed:
                if isinstance(item, dict):
                    logger.warning("Found dict inside list, returning the dict")
                    return item
            # If no dict found in list, create a wrapper dict
            logger.warning("No dict found in list, wrapping in result dict")
            return {"result": parsed}
        else:
            # Wrap non-dict results in a dictionary
            logger.warning(f"Non-dict result ({type(parsed)}), wrapping in result dict")
            return {"result": parsed}
            
    except Exception as e:
        logger.warning(f"JSON parsing failed with json.loads: {e}, trying json_repair")
        try:
            parsed = json_repair.loads(json_str)
            logger.debug(f"json_repair succeeded, type: {type(parsed)}")
            
            # Ensure we return a dictionary
            if isinstance(parsed, dict):
                return parsed
            elif isinstance(parsed, list) and len(parsed) > 0:
                # If it's a list, try to find the first dictionary in it
                for item in parsed:
                    if isinstance(item, dict):
                        logger.warning("Found dict inside list from json_repair, returning the dict")
                        return item
                # If no dict found in list, create a wrapper dict
                logger.warning("No dict found in list from json_repair, wrapping in result dict")
                return {"result": parsed}
            else:
                # Wrap non-dict results in a dictionary
                logger.warning(f"Non-dict result from json_repair ({type(parsed)}), wrapping in result dict")
                return {"result": parsed}
                
        except Exception as repair_error:
            logger.error(f"Both json.loads and json_repair failed: {repair_error}")
            # Return a default error dict
            return {
                "error": "Failed to parse JSON",
                "original_content": json_str[:500] + "..." if len(json_str) > 500 else json_str
            }


def validate_json_structure(data: Dict[str, Any], required_keys: list = None) -> bool:
    """
    Validate that a JSON structure contains required keys and has expected format.
    
    Args:
        data (Dict[str, Any]): The parsed JSON data to validate
        required_keys (list, optional): List of required keys to check for
        
    Returns:
        bool: True if validation passes, False otherwise
    """
    if not isinstance(data, dict):
        logger.warning(f"Data is not a dictionary: {type(data)}")
        return False
    
    if required_keys:
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            logger.warning(f"Missing required keys: {missing_keys}")
            return False
    
    return True


def clean_json_string(json_str: str) -> str:
    """
    Clean a JSON string by removing common formatting issues.
    
    Args:
        json_str (str): The JSON string to clean
        
    Returns:
        str: The cleaned JSON string
    """
    # Remove leading/trailing whitespace
    cleaned = json_str.strip()
    
    # Replace non-breaking spaces
    cleaned = cleaned.replace("\xa0", " ")
    
    # Remove any BOM characters
    cleaned = cleaned.replace("\ufeff", "")
    
    # Fix common escape sequence issues
    cleaned = cleaned.replace("\\n", "\n")
    cleaned = cleaned.replace("\\t", "\t")
    
    return cleaned
