from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.utils.logger import logger

router = APIRouter()
chat_service = ChatService()

@router.post("/chat/stream")
async def stream_chat(request: ChatRequest):
    """
    流式聊天API端点
    """
    try:
        logger.info(f"Stream chat request received: {request.message[:100]}...")
        
        return StreamingResponse(
            chat_service.stream_chat(request),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            }
        )
    except Exception as e:
        logger.error(f"Error in stream_chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/chat", response_model=ChatResponse)
async def simple_chat(request: ChatRequest):
    """
    简单聊天API端点（非流式）
    """
    try:
        logger.info(f"Simple chat request received: {request.message[:100]}...")
        
        response_text = await chat_service.simple_chat(request)
        
        return ChatResponse(
            response=response_text,
            model=request.model
        )
    except Exception as e:
        logger.error(f"Error in simple_chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/chat/models")
async def get_available_models():
    """
    获取可用的聊天模型列表
    """
    models = [
        {
            "value": "claude-3-5-sonnet-20241022",
            "label": "Claude 3.5 Sonnet",
            "description": "最新版本，平衡性能与速度"
        },
        {
            "value": "claude-3-7",
            "label": "Claude 3.7",
            "description": "更强性能，适合复杂推理任务"
        },
        {
            "value": "claude-4-0",
            "label": "Claude 4.0",
            "description": "最新最强版本，顶级性能"
        }
    ]
    return {"models": models}