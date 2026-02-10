# RSS Sync Lambda with AgentCore Browser

This Lambda function demonstrates how to use AWS Bedrock AgentCore browser capabilities to scrape web content at scale. It processes RSS feeds and downloads full article content including HTML, images, and screenshots.

## AgentCore Browser Integration

### Key Components

```python
from bedrock_agentcore.tools.browser_client import browser_session
from playwright.sync_api import sync_playwright
```

### Browser Session Setup

```python
# 1. Create Playwright context
with sync_playwright() as playwright:
    
    # 2. Initialize AgentCore browser session
    with browser_session(CONFIG["BROWSER_REGION"]) as client:
        
        # 3. Generate WebSocket connection
        ws_url, headers = client.generate_ws_headers()
        
        # 4. Connect via Chrome DevTools Protocol
        chromium = playwright.chromium
        browser = chromium.connect_over_cdp(ws_url, headers=headers)
        page = browser.new_page()
```

### Why AgentCore Browser?

- **Serverless**: No need to manage browser instances
- **Scalable**: Handles concurrent browser sessions automatically  
- **Cost-effective**: Pay per use, no idle browser costs
- **Managed**: AWS handles browser lifecycle and updates

## Usage

### Environment Variables

```bash
S3_BUCKET=your-bucket-name
BROWSER_REGION=us-east-1
LOG_LEVEL=20
HOURS_BACK=24
REQUEST_TIMEOUT=30
MAX_IMAGE_SIZE=5242880
PAGE_WAIT_TIME=5
```

### Lambda Event Format

```json
{
  "rss_feed_url": "https://example.com/feed.xml",
  "hours_back": 24,
  "download_images": true
}
```

### Response Format

```json
{
  "statusCode": 200,
  "body": {
    "message": "RSS sync completed successfully",
    "articles_processed": 5,
    "images_downloaded": 23,
    "hours_back": 24
  }
}
```

## Architecture

```
RSS Feed → Parse Articles → AgentCore Browser → Scrape Content → S3 Storage
                                ↓
                        [HTML + Screenshots + Images]
```

## S3 Output Structure

```
bucket/
├── hostname.com/
│   └── article_hash/
│       ├── article.html
│       ├── screenshot.png
│       ├── metadata.json
│       └── images/
│           ├── image1.jpg
│           └── image2.png
```

## Key Features

- **Intelligent Retry**: Exponential backoff with jitter
- **Duplicate Detection**: Skip already processed articles
- **Resource Cleanup**: Proper browser session management
- **Error Resilience**: Continue processing on individual failures
- **Performance Optimization**: Longer timeouts for first article

## Best Practices

1. **Always use context managers** for browser sessions
2. **Implement proper cleanup** in finally blocks
3. **Add exponential backoff** for network operations
4. **Cache expensive operations** like S3 client creation
5. **Use structured logging** for better observability

## Deployment

This function requires:
- Bedrock AgentCore permissions
- S3 read/write permissions
- VPC configuration (if needed)
- Sufficient memory (1GB+ recommended)
- Extended timeout (15 minutes for large feeds)

## Error Handling

The function implements multiple layers of error handling:
- Network timeouts with fallback strategies
- Browser readiness checks with retry logic
- Individual article failure isolation
- Graceful resource cleanup on errors
