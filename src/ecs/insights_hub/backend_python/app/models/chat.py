from typing import List, Optional
from pydantic import BaseModel

class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str

class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[ChatMessage]] = []
    model: Optional[str] = "claude-3-5-sonnet-20241022"

class ChatResponse(BaseModel):
    response: str
    model: str

class StreamChunk(BaseModel):
    chunk: Optional[str] = None
    done: Optional[bool] = False
    error: Optional[str] = None