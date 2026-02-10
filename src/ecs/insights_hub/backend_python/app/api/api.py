from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import designs, chat
from app.core.config import settings
import os
import logging
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# 设置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头部
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    
    # Log request details
    logger.info(f"Request start: {request.method} {request.url.path}")
    logger.info(f"Request headers: {dict(request.headers)}")
    
    # Process the request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = (datetime.now() - start_time).total_seconds()
    
    # Log response details
    logger.info(f"Request completed: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.4f}s")
    
    return response

# 添加健康检查端点（不在API前缀下）
@app.get("/health")
async def health_check():
    """健康检查端点，用于ECS负载均衡器"""
    logger.info("Health check endpoint called")
    return {"status": "healthy"}

# 添加认证配置端点
@app.get("/api/auth/config")
async def get_auth_config():
    """Return Cognito configuration for frontend authentication"""
    try:
        # Get configuration from environment variables
        user_pool_id = os.getenv("COGNITO_USER_POOL_ID", "insights-jiatinUser")
        client_id = os.getenv("COGNITO_CLIENT_ID", "insights-jiatinClient")
        region = os.getenv("COGNITO_REGION", os.getenv("AWS_REGION", "us-east-1"))
        
        # Log the configuration
        logger.info(f"Auth config requested - Pool ID: {user_pool_id}, Client ID: {client_id}, Region: {region}")
        
        # Check if configuration is valid
        if not user_pool_id or not client_id:
            logger.warning("Incomplete Cognito configuration")
            return {"error": "Authentication configuration is not available"}, 500
        
        # Return the configuration
        auth_config = {
            "userPoolId": user_pool_id,
            "clientId": client_id,
            "region": region,
        }
        
        logger.info(f"Auth config response: {json.dumps(auth_config)}")
        return auth_config
    except Exception as e:
        logger.error(f"Error in get_auth_config: {str(e)}", exc_info=True)
        return {"error": f"Internal server error: {str(e)}"}, 500

# 包含路由
app.include_router(designs.router, prefix=settings.API_V1_STR)
app.include_router(chat.router, prefix=settings.API_V1_STR)
