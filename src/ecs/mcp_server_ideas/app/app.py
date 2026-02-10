import logging
import os
import uvicorn


# Configure logging
log_level = int(os.environ.get("LOG_LEVEL", logging.INFO))
logging.basicConfig(level=log_level, format="%(levelname)s: - %(name)s - %(message)s")
logger = logging.getLogger("mcp-app")
logger.info(f"Starting MCP server with log level: {log_level}")





# Entry point for running the server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))

    # Run the server with uvicorn
    # In production, we use the environment variable to determine the host
    # In containerized environments, we need to bind to 0.0.0.0
    # In local development, we can bind to localhost for better security
    host = os.environ.get("SERVER_HOST", "127.0.0.1")

    from server import mcp_server  # Import the MCP server from server.py

    app = mcp_server.http_app()

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=logging.WARNING,
        timeout_keep_alive=65,  # ALB timeout is usually 60s
        access_log=True,  # Enable access logging
    )
