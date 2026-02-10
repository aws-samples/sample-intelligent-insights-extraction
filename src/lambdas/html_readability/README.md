# JavaScript Readability Lambda

This Lambda function uses Mozilla's original JavaScript Readability library to process HTML content and extract the main content in a clean, readable format.


## Usage


Invoke the Lambda with HTML content:

```bash
aws lambda invoke --function-name JSReadabilityFunction \
  --payload '{"html_content": "<html><body><h1>Title</h1><p>Content</p></body></html>"}' \
  output.json
```

## Dependencies

- @mozilla/readability: The official Mozilla Readability library
- jsdom: DOM implementation for Node.js (required by Readability)

## Configuration

The Lambda function can be configured with the following environment variables:

- `LOG_LEVEL`: Set the logging level (DEBUG, INFO, WARN, ERROR)
