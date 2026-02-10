# RSS Sync Lambda Function
# Reads RSS feeds, downloads HTML content and images using Playwright

import boto3
import json
import logging
import os
import requests
import fastfeedparser
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse, urljoin, urlunparse
import hashlib
import traceback

import time
import random

# CRITICAL IMPORT SECTION - This is where the error occurs

from playwright.sync_api import sync_playwright, Playwright, BrowserType, Page
from bedrock_agentcore.tools.browser_client import browser_session


logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s"
)


log_level = int(os.environ.get("LOG_LEVEL", logging.DEBUG))

logger = logging.getLogger("rss_sync")
logger.setLevel(log_level)

# Configuration settings
CONFIG = {
    "HOURS_BACK": int(
        os.environ.get("HOURS_BACK", "24")
    ),  # Hours back to consider "recent"
    "REQUEST_TIMEOUT": int(
        os.environ.get("REQUEST_TIMEOUT", "30")
    ),  # Request timeout in seconds
    "MAX_IMAGE_SIZE": int(
        os.environ.get("MAX_IMAGE_SIZE", "5242880")
    ),  # Max image size (5MB)
    "BROWSER_REGION": os.environ.get(
        "BROWSER_REGION", "us-east-1"
    ),  # Browser session region
    "PAGE_WAIT_TIME": int(
        os.environ.get("PAGE_WAIT_TIME", "5")
    ),  # Time to wait for page load
}


def wait_for_browser_ready(
    page: Page, max_attempts: int = 5, base_delay: float = 1.0, max_delay: float = 10.0
) -> bool:
    """Wait for browser to be ready using exponential backoff with jitter

    Args:
        page: Playwright page object
        max_attempts: Maximum number of attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        True if browser is ready, False if timeout
    """
    for attempt in range(max_attempts):
        try:
            # Test browser readiness with a simple JavaScript evaluation
            result = page.evaluate("() => ({ ready: true, timestamp: Date.now() })")
            if result and result.get("ready"):
                logger.info(f"Browser ready after {attempt + 1} attempts")
                return True
        except Exception as e:
            logger.debug(f"Browser readiness check {attempt + 1} failed: {str(e)}")

        if attempt < max_attempts - 1:  # Don't sleep on last attempt
            # Exponential backoff with jitter
            delay = min(base_delay * (2**attempt), max_delay)
            jitter = random.uniform(0, 0.1 * delay)  # Add up to 10% jitter
            total_delay = delay + jitter

            logger.debug(
                f"Browser not ready, waiting {total_delay:.2f}s (attempt {attempt + 1}/{max_attempts})"
            )
            time.sleep(total_delay)

    logger.warning(f"Browser readiness timeout after {max_attempts} attempts")
    return False


def wait_for_page_ready(
    page: Page, max_attempts: int = 10, base_delay: float = 0.5, max_delay: float = 5.0
) -> bool:
    """Wait for page to be ready using exponential backoff

    Args:
        page: Playwright page object
        max_attempts: Maximum number of attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        True if page is ready, False if timeout
    """
    for attempt in range(max_attempts):
        try:
            # Check if page is ready by evaluating document state
            result = page.evaluate(
                """
                () => {
                    return {
                        readyState: document.readyState,
                        hasTitle: !!document.title,
                        hasBody: !!document.body,
                        imagesLoaded: document.images.length === 0 || 
                                     Array.from(document.images).every(img => img.complete),
                        timestamp: Date.now()
                    };
                }
            """
            )

            if (
                result
                and result.get("readyState") in ["interactive", "complete"]
                and result.get("hasTitle")
                and result.get("hasBody")
            ):

                logger.info(
                    f"Page ready after {attempt + 1} attempts (state: {result.get('readyState')})"
                )
                return True

        except Exception as e:
            logger.debug(f"Page readiness check {attempt + 1} failed: {str(e)}")

        if attempt < max_attempts - 1:  # Don't sleep on last attempt
            # Exponential backoff with jitter
            delay = min(base_delay * (2**attempt), max_delay)
            jitter = random.uniform(0, 0.1 * delay)  # Add up to 10% jitter
            total_delay = delay + jitter

            logger.debug(
                f"Page not ready, waiting {total_delay:.2f}s (attempt {attempt + 1}/{max_attempts})"
            )
            time.sleep(total_delay)

    logger.warning(f"Page readiness timeout after {max_attempts} attempts")
    return False


def wait_for_network_idle(
    page: Page,
    max_attempts: int = 8,
    base_delay: float = 0.5,
    max_delay: float = 3.0,
    idle_time: float = 1.0,
) -> bool:
    """Wait for network to be idle using exponential backoff

    Args:
        page: Playwright page object
        max_attempts: Maximum number of attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        idle_time: Required idle time in seconds

    Returns:
        True if network is idle, False if timeout
    """
    last_request_count = 0
    stable_count = 0
    required_stable_checks = max(2, int(idle_time / base_delay))

    for attempt in range(max_attempts):
        try:
            # Check network activity by counting requests
            current_count = page.evaluate(
                """
                () => {
                    // Count active network requests (approximation)
                    const performanceEntries = performance.getEntriesByType('navigation').length +
                                             performance.getEntriesByType('resource').length;
                    return performanceEntries;
                }
            """
            )

            if current_count == last_request_count:
                stable_count += 1
                if stable_count >= required_stable_checks:
                    logger.info(f"Network idle detected after {attempt + 1} attempts")
                    return True
            else:
                stable_count = 0
                last_request_count = current_count

        except Exception as e:
            logger.debug(f"Network idle check {attempt + 1} failed: {str(e)}")

        if attempt < max_attempts - 1:  # Don't sleep on last attempt
            # Exponential backoff with jitter
            delay = min(base_delay * (1.5**attempt), max_delay)
            jitter = random.uniform(0, 0.1 * delay)
            total_delay = delay + jitter

            logger.debug(
                f"Network not idle, waiting {total_delay:.2f}s (attempt {attempt + 1}/{max_attempts})"
            )
            time.sleep(total_delay)

    logger.warning(f"Network idle timeout after {max_attempts} attempts")
    return False


def normalize_url(url: str) -> str:
    """Normalize URL to ensure consistent hashing

    Args:
        url (str): Original URL

    Returns:
        str: Normalized URL
    """
    try:
        # Parse the URL
        parsed = urlparse(url)

        # Normalize the components
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip(
            "/"
        ).lower()  # Remove trailing slash and lowercase path

        # Remove common tracking parameters
        query = parsed.query
        if query:
            # Remove common tracking parameters
            tracking_params = {
                "utm_source",
                "utm_medium",
                "utm_campaign",
                "utm_term",
                "utm_content",
                "fbclid",
                "gclid",
                "msclkid",
                "ref",
                "source",
                "campaign",
            }
            query_parts = []
            for param in query.split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    if key.lower() not in tracking_params:
                        query_parts.append(param)
                else:
                    query_parts.append(param)
            query = "&".join(query_parts)

        # Ignore fragments (everything after #)
        fragment = ""

        # Reconstruct normalized URL
        normalized = urlunparse((scheme, netloc, path, parsed.params, query, fragment))

        return normalized

    except Exception as e:
        # If normalization fails, return original URL
        logger.warning(f"URL normalization failed for {url}: {str(e)}")
        return url


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """RSS Sync Lambda Handler with Playwright

    This Lambda function can either:
    1. Process an RSS feed and scrape all articles
    2. Scrape a single webpage URL

    Then saves everything to S3.
    """
    try:
        logger.info("🚀 LAMBDA HANDLER STARTED")
        logger.info(f"📥 Event received: {json.dumps(event, default=str)}")

        # Check if this is a single page scrape or RSS feed processing
        logger.info("📋 Extracting parameters from event...")

        # RSS feed processing mode
        rss_feed_url = event.get("rss_feed_url")
        bucket_name = os.environ.get("S3_BUCKET", "default-rss-scrape-bucket")
        if bucket_name == "default-rss-scrape-bucket":
            logger.warning(
                "⚠️ Using default bucket name. Set S3_BUCKET environment variable for production."
            )
        else:
            logger.info(f"📦 Using configured S3 bucket: {bucket_name}")
        hours_back = event.get("hours_back", CONFIG["HOURS_BACK"])
        download_images = event.get("download_images", True)

        logger.info(f"📊 Parameters extracted:")
        logger.info(f"   - RSS Feed URL: {rss_feed_url}")
        logger.info(f"   - Bucket Name: {bucket_name}")
        logger.info(f"   - Hours Back: {hours_back}")
        logger.info(f"   - Download Images: {download_images}")

        if not rss_feed_url:
            error_msg = "RSS_FEED_URL environment variable is required"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        logger.info(f"🎭 Starting RSS sync with Playwright for feed: {rss_feed_url}")

        # Process RSS feed and download content using Playwright
        logger.info("🔄 Calling process_rss_feed_with_playwright...")
        try:
            feed_data = process_rss_feed_with_playwright(
                rss_feed_url, hours_back, download_images
            )
            logger.info("✅ process_rss_feed_with_playwright completed successfully")
        except Exception as e:
            logger.error(f"❌ process_rss_feed_with_playwright FAILED: {str(e)}")
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            raise Exception(f"Failed to process RSS feed: {str(e)}")

        total_items = len(feed_data.get("items", []))
        total_images = sum(
            len(item.get("images", [])) for item in feed_data.get("items", [])
        )

        logger.info(
            f"📈 Processing completed: {total_items} articles with {total_images} images downloaded"
        )

        response_body = {
            "message": "RSS sync with Playwright completed successfully",
            "rss_feed_url": rss_feed_url,
            "articles_processed": total_items,
            "images_downloaded": total_images,
            "hours_back": hours_back,
        }

        logger.info("✅ LAMBDA HANDLER COMPLETED SUCCESSFULLY")
        return {"statusCode": 200, "body": json.dumps(response_body)}

    except Exception as e:
        error_msg = f"Error in lambda handler: {str(e)}"
        logger.error(f"❌ LAMBDA HANDLER FAILED: {error_msg}")
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": str(e),
                    "message": "Lambda execution failed",
                    "traceback": traceback.format_exc(),
                }
            ),
        }


def process_rss_feed_with_playwright(
    rss_feed_url: str, hours_back: int, download_images: bool = True
) -> Dict[str, Any]:
    """Process RSS feed and download full content using Playwright

    Args:
        rss_feed_url (str): RSS feed URL
        hours_back (int): Number of hours back to consider items as recent
        download_images (bool): Whether to download images from articles

    Returns:
        Dict[str, Any]: Dictionary containing processed feed data with full content
    """
    cutoff_time = datetime.now(UTC) - timedelta(hours=hours_back)

    try:
        logger.info(f"🔍 Processing RSS feed: {rss_feed_url}")

        # Fetch and parse RSS feed
        logger.info("📡 Fetching and parsing RSS feed...")
        try:
            feed_data = fetch_and_parse_rss_feed(rss_feed_url, cutoff_time)
            logger.info(
                f"✅ RSS feed parsed successfully: {len(feed_data.get('items', []))} items found"
            )
        except Exception as e:
            raise Exception(f"Failed to fetch RSS feed: {str(e)}")

        # Process each article with Playwright
        enriched_items = []

        logger.info("🎭 Starting Playwright browser session...")
        with sync_playwright() as playwright:
            logger.debug("✅ Playwright context created successfully")

            with browser_session(CONFIG["BROWSER_REGION"]) as client:
                logger.debug("🔗 Generating WebSocket headers...")

                ws_url, headers = client.generate_ws_headers()
                logger.debug(f"✅ WebSocket URL generated: {ws_url[:50]}...")

                # Connect to browser
                logger.info("🔌 Connecting to browser via CDP...")
                chromium: BrowserType = playwright.chromium
                browser = chromium.connect_over_cdp(ws_url, headers=headers)
                page = browser.new_page()
                logger.info("✅ Browser connected successfully")

                try:
                    # Warmup the browser with intelligent backoff
                    # logger.info("🔥 Warming up browser session...")
                    # try:
                    #     page.goto("about:blank", timeout=10000)
                    #     # Wait for browser to be ready using exponential backoff
                    #     if wait_for_browser_ready(page):
                    #         logger.info("✅ Browser warmup completed successfully")
                    #     else:
                    #         logger.warning(
                    #             "⚠️ Browser warmup timeout, continuing anyway"
                    #         )
                    # except Exception as e:
                    #     logger.warning(f"⚠️ Browser warmup failed: {str(e)}")

                    logger.info(
                        f"📰 Processing {len(feed_data.get('items', []))} articles..."
                    )
                    for i, item in enumerate(feed_data.get("items", []), 1):
                        article_url = item.get("link")
                        if article_url:
                            try:
                                logger.info(
                                    f"📄 Processing article {i}/{len(feed_data.get('items', []))}: {article_url}"
                                )

                                # Use longer timeout for first article
                                is_first_article = i == 1
                                article_data = scrape_article_with_playwright(
                                    page,
                                    article_url,
                                    download_images,
                                    is_first_article,
                                )

                                # Merge article data with RSS item data
                                item.update(article_data)

                                # Check if article was skipped (already exists)
                                if article_data.get("skipped", False):
                                    item["content_downloaded"] = "skipped"
                                    item["skip_reason"] = article_data.get(
                                        "skip_reason", "Unknown"
                                    )
                                    logger.info(
                                        f"⏭️ Article {i} skipped: {article_data.get('skip_reason', 'Already exists')}"
                                    )
                                else:
                                    item["content_downloaded"] = True
                                    logger.info(
                                        f"✅ Article {i} processed successfully"
                                    )

                            except Exception as e:
                                logger.warning(
                                    f"⚠️ Error processing article {article_url}: {str(e)}"
                                )
                                logger.warning(f"⚠️ Traceback: {traceback.format_exc()}")
                                item["content_downloaded"] = False
                                item["content_error"] = str(e)

                        enriched_items.append(item)

                finally:
                    logger.info("🧹 Cleaning up browser resources...")
                    try:
                        page.close()
                        browser.close()
                        logger.info("✅ Browser resources cleaned up successfully")
                    except Exception as e:
                        logger.warning(f"⚠️ Error during browser cleanup: {str(e)}")

    except Exception as e:
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        raise Exception(f"Failed to process RSS feed: {str(e)}")


def if_content_exist(bucket_name: str, file_key: str) -> bool:
    s3 = boto3.resource("s3")
    try:
        s3.Object(bucket_name, file_key).load()
        return True
    except Exception as e:

        logger.warning(f"Error: {e}")
        return False


def generate_article_paths(article_url: str) -> Tuple[str, str, str]:
    """Generate S3 paths for article content

    Args:
        article_url: URL of the article

    Returns:
        Tuple of (hostname, url_hash, s3_prefix)
    """
    parsed_url = urlparse(article_url)
    hostname = parsed_url.netloc
    url_hash = hashlib.md5(normalize_url(article_url).encode(), usedforsecurity=False).hexdigest()[:12]
    s3_prefix = f"{hostname}/{url_hash}"

    logger.debug(f"Web url: {article_url} Hash: {url_hash}")
    logger.debug(f"📁 S3 prefix: {s3_prefix}")

    return hostname, url_hash, s3_prefix


def check_existing_article(
    bucket_name: str, s3_prefix: str, hostname: str, url_hash: str
) -> Optional[Dict[str, Any]]:
    """Check if article already exists in S3

    Args:
        bucket_name: S3 bucket name
        s3_prefix: S3 prefix for the article
        hostname: Hostname from URL
        url_hash: Hash of the URL

    Returns:
        Article data if exists, None otherwise
    """
    html_s3_key = f"{s3_prefix}/article.html"

    if if_content_exist(bucket_name, html_s3_key):
        return {
            "folder_name": f"{hostname}_{url_hash}",
            "s3_prefix": s3_prefix,
            "title": "Existing Article (not re-downloaded)",
            "html_content": "",
            "html_size": 0,
            "html_s3_key": html_s3_key,
            "rendered_content": {},
            "images": [],
            "images_count": 0,
            "screenshot_s3_key": f"{s3_prefix}/screenshot.png",
            "metadata_s3_key": f"{s3_prefix}/metadata.json",
            "metadata": {},
            "skipped": True,
            "skip_reason": "Article already exists in S3",
        }
    return None


def navigate_to_page(page: Page, article_url: str, is_first_article: bool) -> None:
    """Navigate to article page with appropriate timeouts

    Args:
        page: Playwright page object
        article_url: URL to navigate to
        is_first_article: Whether this is the first article (longer timeout)
    """
    timeout = 60000 if is_first_article else 30000
    logger.info(f"🌐 Navigating to {article_url}")
    logger.info(f"⏱️ Using timeout: {timeout}ms")

    try:
        page.goto(article_url, wait_until="networkidle", timeout=timeout)
    except Exception as e:
        if "Timeout" in str(e):
            logger.warning(
                f"⚠️ Networkidle timeout, trying with domcontentloaded: {str(e)}"
            )
            page.goto(article_url, wait_until="domcontentloaded", timeout=timeout)
        else:
            raise e


def capture_page_content(
    page: Page, s3_client: Any, bucket_name: str, s3_prefix: str
) -> Tuple[str, str, str]:
    """Capture page content and upload to S3

    Args:
        page: Playwright page object
        s3_client: Boto3 S3 client
        bucket_name: S3 bucket name
        s3_prefix: S3 prefix for uploads

    Returns:
        Tuple of (page_title, html_content, html_s3_key)
    """
    # Get page title
    page_title = page.evaluate("() => document.title")

    # Take screenshot
    logger.info("📸 Taking screenshot...")
    screenshot_bytes = page.screenshot(full_page=True)
    screenshot_s3_key = f"{s3_prefix}/screenshot.png"

    s3_client.put_object(
        Bucket=bucket_name,
        Key=screenshot_s3_key,
        Body=screenshot_bytes,
        ContentType="image/png",
    )
    logger.info(f"✅ Screenshot uploaded to s3://{bucket_name}/{screenshot_s3_key}")

    # Get HTML content
    html_content = page.evaluate("() => document.documentElement.outerHTML")
    html_s3_key = f"{s3_prefix}/article.html"

    s3_client.put_object(
        Bucket=bucket_name,
        Key=html_s3_key,
        Body=html_content.encode("utf-8"),
        ContentType="text/html; charset=utf-8",
    )
    logger.info(f"✅ HTML uploaded to s3://{bucket_name}/{html_s3_key}")

    return page_title, html_content, html_s3_key


def create_and_upload_metadata(
    s3_client: Any,
    bucket_name: str,
    s3_prefix: str,
    article_url: str,
    page_title: str,
    folder_name: str,
    html_s3_key: str,
    images_data: List[Dict[str, Any]],
) -> str:
    """Create and upload article metadata to S3

    Args:
        s3_client: Boto3 S3 client
        bucket_name: S3 bucket name
        s3_prefix: S3 prefix
        article_url: Original article URL
        page_title: Page title
        folder_name: Folder name
        html_s3_key: HTML S3 key
        images_data: List of image data

    Returns:
        Metadata S3 key
    """
    metadata = {
        "original_url": article_url,
        "title": page_title,
        "folder_name": folder_name,
        "s3_prefix": s3_prefix,
        "timestamp": datetime.now(UTC).isoformat(),
        "html_s3_key": html_s3_key,
        "screenshot_s3_key": f"{s3_prefix}/screenshot.png",
        "images": images_data,
    }

    metadata_s3_key = f"{s3_prefix}/metadata.json"
    s3_client.put_object(
        Bucket=bucket_name,
        Key=metadata_s3_key,
        Body=json.dumps(metadata, indent=2, ensure_ascii=False, default=str),
        ContentType="application/json",
    )
    logger.info(f"✅ Metadata uploaded to s3://{bucket_name}/{metadata_s3_key}")

    return metadata_s3_key


def scrape_article_with_playwright(
    page: Page,
    article_url: str,
    download_images: bool = True,
    is_first_article: bool = False,
) -> Dict[str, Any]:
    """Use Playwright to scrape article content and upload directly to S3

    Args:
        page: Playwright page object
        article_url: URL of the article to scrape
        download_images: Whether to download images
        is_first_article: Whether this is the first article (longer timeout)

    Returns:
        Scraped content and S3 upload info
    """
    s3_client = boto3.client("s3")
    bucket_name = os.environ.get("S3_BUCKET")

    try:
        # Generate paths and check if article exists
        hostname, url_hash, s3_prefix = generate_article_paths(article_url)

        existing_article = check_existing_article(
            bucket_name, s3_prefix, hostname, url_hash
        )
        if existing_article:
            return existing_article

        folder_name = f"{hostname}_{url_hash}"

        # Navigate to page
        navigate_to_page(page, article_url, is_first_article)

        # Wait for page to be ready
        logger.info("⏳ Waiting for page to be ready...")
        if not wait_for_page_ready(page):
            logger.warning("⚠️ Page readiness timeout, continuing anyway")

        # Capture page content
        page_title, html_content, html_s3_key = capture_page_content(
            page, s3_client, bucket_name, s3_prefix
        )

        # Download images if enabled
        images_data = []
        if download_images:
            logger.info("🖼️ Processing images...")
            images_data = download_images_to_s3(
                page, article_url, s3_client, bucket_name, f"{s3_prefix}/images"
            )

        # Create and upload metadata
        metadata_s3_key = create_and_upload_metadata(
            s3_client,
            bucket_name,
            s3_prefix,
            article_url,
            page_title,
            folder_name,
            html_s3_key,
            images_data,
        )

        return {
            "folder_name": folder_name,
            "s3_prefix": s3_prefix,
            "title": page_title,
            "html_content": html_content,
            "html_size": len(html_content),
            "html_s3_key": html_s3_key,
            "images": images_data,
            "images_count": len(images_data),
            "screenshot_s3_key": f"{s3_prefix}/screenshot.png",
            "metadata_s3_key": metadata_s3_key,
            "metadata": {},
        }

    except Exception as e:
        logger.warning(f"❌ Error scraping article {article_url}: {str(e)}")
        logger.warning(f"❌ Traceback: {traceback.format_exc()}")
        return {
            "folder_name": "",
            "s3_prefix": "",
            "title": "",
            "html_content": "",
            "html_size": 0,
            "html_s3_key": "",
            "rendered_content": {},
            "images": [],
            "images_count": 0,
            "screenshot_s3_key": "",
            "metadata_s3_key": "",
            "metadata": {},
            "error": str(e),
        }


def download_images_to_s3(
    page: Page, base_url: str, s3_client: Any, bucket_name: str, s3_images_prefix: str
) -> List[Dict[str, Any]]:
    """Download all images from the page and upload directly to S3

    Args:
        page: Playwright page object
        base_url (str): Base URL for resolving relative URLs
        s3_client: Boto3 S3 client
        bucket_name (str): S3 bucket name
        s3_images_prefix (str): S3 prefix for images

    Returns:
        List[Dict]: List of image metadata with S3 keys
    """
    images_data = []

    try:
        # Get all img elements using locator
        img_locators = page.locator("img").all()

        logger.info(f"🖼️ Found {len(img_locators)} images on page")

        for i, img_locator in enumerate(img_locators, 1):
            try:
                # Get the image URL from the src attribute
                image_url = img_locator.get_attribute("src")

                if not image_url:
                    # Try alternative attributes
                    image_url = img_locator.get_attribute(
                        "data-src"
                    ) or img_locator.get_attribute("data-lazy-src")

                if image_url:
                    # Resolve relative URLs
                    if image_url.startswith("//"):
                        image_url = "https:" + image_url
                    elif image_url.startswith("/"):
                        parsed_base = urlparse(base_url)
                        image_url = (
                            f"{parsed_base.scheme}://{parsed_base.netloc}{image_url}"
                        )
                    elif not image_url.startswith(("http://", "https://")):
                        image_url = urljoin(base_url, image_url)

                    # Skip data URLs and very small images
                    if image_url.startswith("data:") or "pixel" in image_url.lower():
                        continue

                    # Generate filename
                    parsed_url = urlparse(image_url)
                    original_filename = os.path.basename(parsed_url.path)
                    if not original_filename or "." not in original_filename:
                        original_filename = f"image_{i}.jpg"

                    # Create S3 key
                    image_s3_key = f"{s3_images_prefix}/{original_filename}"

                    # Download the image using requests
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Referer": base_url,
                    }

                    response = requests.get(image_url, timeout=30, headers=headers)
                    if response.status_code == 200:
                        # Check file size
                        if len(response.content) > CONFIG["MAX_IMAGE_SIZE"]:
                            logger.warning(f"⚠️ Image too large: {image_url}")
                            continue

                        # Determine content type
                        content_type = response.headers.get(
                            "content-type", "image/jpeg"
                        )

                        # Upload to S3
                        s3_client.put_object(
                            Bucket=bucket_name,
                            Key=image_s3_key,
                            Body=response.content,
                            ContentType=content_type,
                        )

                        file_size = len(response.content)

                        # Add to images data
                        image_info = {
                            "original_url": image_url,
                            "s3_key": image_s3_key,
                            "s3_url": f"images/{original_filename}",  # Relative path to current folder
                            "filename": original_filename,
                            "size": file_size,
                            "content_type": content_type,
                        }

                        images_data.append(image_info)
                        logger.info(
                            f"✅ Image {i} uploaded: {original_filename} ({file_size:,} bytes) -> s3://{bucket_name}/{image_s3_key}"
                        )

                    else:
                        logger.warning(
                            f"⚠️ Failed to download image. Status code: {response.status_code} for {image_url}"
                        )
                else:
                    logger.debug("🔍 Image URL not found.")

            except Exception as e:
                logger.warning(f"⚠️ Error downloading image {i}: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"❌ Error getting images from page: {str(e)}")

    logger.info(f"📊 Successfully uploaded {len(images_data)} images to S3")
    return images_data


def fetch_and_parse_rss_feed(feed_url: str, cutoff_time: datetime) -> Dict[str, Any]:
    """Fetch and parse a single RSS feed

    Args:
        feed_url (str): RSS feed URL
        cutoff_time (datetime): Only include items newer than this time

    Returns:
        Dict[str, Any]: Parsed feed data with metadata and items
    """
    try:
        # Fetch the RSS feed with timeout
        headers = {"User-Agent": "RSS-Sync-Lambda/1.0 (AWS Lambda RSS Reader)"}

        response = requests.get(
            feed_url, headers=headers, timeout=CONFIG["REQUEST_TIMEOUT"]
        )
        response.raise_for_status()

        # Parse the RSS feed
        feed = fastfeedparser.parse(response.content)

        # Extract feed metadata
        feed_info = {
            "url": feed_url,
            "title": getattr(feed.feed, "title", "Unknown"),
            "description": getattr(feed.feed, "description", ""),
            "link": getattr(feed.feed, "link", ""),
            "language": getattr(feed.feed, "language", ""),
            "last_updated": getattr(feed.feed, "updated", ""),
            "generator": getattr(feed.feed, "generator", ""),
            "total_entries": len(feed.entries),
        }

        # Process feed items
        recent_items = []
        for entry in feed.entries:
            try:
                # Check if item is recent enough
                item_date = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    item_date = datetime(*entry.published_parsed[:6], tzinfo=UTC)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    item_date = datetime(*entry.updated_parsed[:6], tzinfo=UTC)

                # Skip if item is too old
                if item_date and item_date < cutoff_time:
                    continue

                # Extract item data directly
                recent_items.append(
                    {
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "description": entry.get("description", ""),
                        "summary": entry.get("summary", ""),
                        "published": entry.get("published", ""),
                        "updated": entry.get("updated", ""),
                        "published_parsed": getattr(entry, "published_parsed", None),
                        "updated_parsed": getattr(entry, "updated_parsed", None),
                        "author": entry.get("author", ""),
                        "id": entry.get("id", ""),
                        "guid": entry.get("guid", ""),
                        "tags": [
                            tag.get("term", str(tag)) for tag in entry.get("tags", [])
                        ],
                        "categories": entry.get("categories", []),
                        "content": (
                            [
                                {
                                    "type": c.get("type", "text/html"),
                                    "value": c.get("value", ""),
                                }
                                for c in entry.get("content", [])
                            ]
                            if "content" in entry
                            else []
                        ),
                    }
                )

            except Exception as e:
                logger.warning(f"❌ Error processing entry: {str(e)} ignore entry")

        return {
            "feed_info": feed_info,
            "items": recent_items,
            "items_count": len(recent_items),
            "processed_at": datetime.now(UTC).isoformat(),
        }

    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch RSS feed: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to parse RSS feed: {str(e)}")


# def main():
#     """Main function for testing - calls lambda_handler with test event"""
#     # Setup logging for local testing
#     os.environ["S3_BUCKET"] = "insights-michelle-sourcebucketddd2130a-buikkrwm7di3"
#
#     # Create test event with RSS feed URL
#     test_feed_url = "https://fashionbombdaily.com/feed/"
#
#     test_feed_url = "https://www.thewesternoutfitters.com/blog/feed/"
#
#     event = {
#         "rss_feed_url": test_feed_url,
#         "hours_back": 24,
#         "download_images": True,
#         # Note: bucket_name not included for local testing (will skip S3 save)
#     }
#
#     print("Testing RSS feed processing via lambda_handler...")
#     print(f"RSS Feed: {test_feed_url}")
#     print("Working Directory:", os.getcwd())
#     print(f"Event: {json.dumps(event, indent=2)}")
#
#     try:
#         # Call lambda_handler with test event
#         print("\n🎭 Calling lambda_handler...")
#         result = lambda_handler(event, context=None)
#
#         print(f"\n✅ Lambda handler completed!")
#         print(f"Status Code: {result['statusCode']}")
#
#         if result["statusCode"] == 200:
#             body = json.loads(result["body"])
#             print(f"Message: {body['message']}")
#             print(f"Articles processed: {body.get('articles_processed', 0)}")
#             print(f"Images downloaded: {body.get('images_downloaded', 0)}")
#             print(f"Hours back: {body.get('hours_back', 0)}")
#
#             if "s3_location" in body:
#                 print(f"S3 Location: {body['s3_location']}")
#             else:
#                 print("S3 Location: Not saved (no bucket_name in test event)")
#         else:
#             body = json.loads(result["body"])
#             print(f"Error: {body.get('error', 'Unknown error')}")
#             print(f"Message: {body.get('message', 'No message')}")
#
#         return result["statusCode"] == 200
#
#     except Exception as e:
#         print(f"❌ Lambda handler failed!")
#         print(f"Error: {str(e)}")
#         import traceback
#
#         traceback.print_exc()
#         return False
#
#
# if __name__ == "__main__":
#     main()
