# Insights Hub Backend (Python)

A Flask backend for the Insights Design Hub.

## Features

- RESTful API for design data
- Integration with AWS OpenSearch Serverless
- Mock data fallback for development
- Comprehensive error handling and logging

## Prerequisites

- Python 3.8+
- AWS credentials configured (for OpenSearch Serverless access)

## Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Running the Application

Start the development server:

```bash
python app.py
```

The API will be available at http://localhost:3001

## API Endpoints

- `GET /api/designs` - Get all designs with optional filtering
  - Query parameters:
    - `tag` (optional): Filter designs by tag
    - `limit` (optional, default: 20): Number of designs to return
    - `page` (optional, default: 1): Page number

- `GET /api/designs/{design_id}` - Get a design by ID

- `GET /api/designs/search?q={query}` - Search designs by query string

## Development

The application uses mock data when OpenSearch is not available, making it easy to develop without a live OpenSearch instance.
