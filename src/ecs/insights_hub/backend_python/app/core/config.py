import os
from dotenv import load_dotenv
from pathlib import Path

# 从.env文件加载环境变量
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class Settings:
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "Insights Hub API"
    
    # AWS配置
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    OPENSEARCH_COLLECTION_ENDPOINT: str = os.getenv("OPENSEARCH_ENDPOINT", "https://rq48rkc55.us-east-1.aoss.amazonaws.com")
    OPENSEARCH_INDEX: str = os.getenv("OPENSEARCH_INDEX", "content")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "insights-jiatin-sourcebucketddd2130a")
    # 日志
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()
