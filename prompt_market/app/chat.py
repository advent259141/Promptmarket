from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Dict, Optional
import httpx
import json
from pydantic import BaseModel

from . import models, schemas
from .database import get_db
from .auth import get_current_user
from .config import KIMI_API_KEY, KIMI_API_URL

# 聊天相关的模型定义
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    prompt_id: int
    message: str

class ChatResponse(BaseModel):
    response: str
    conversation_id: str

# 创建聊天路由
chat_router = APIRouter()

# 存储用户的对话历史（内存存储，实际应用中考虑使用Redis等）
# 格式: {user_id: {conversation_id: [messages]}}
user_conversations = {}

# 辅助函数：为新用户创建对话历史存储空间
def ensure_user_conversation_store(user_id: int, conversation_id: str):
    if user_id not in user_conversations:
        user_conversations[user_id] = {}
    
    if conversation_id not in user_conversations[user_id]:
        user_conversations[user_id][conversation_id] = []
    
    return user_conversations[user_id][conversation_id]

# 聊天接口
@chat_router.post("/chat/", response_model=ChatResponse)
async def chat_with_prompt(
    chat_request: ChatRequest,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 验证用户是否已登录
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户未登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 获取Prompt内容
    result = await db.execute(select(models.Prompt).filter(models.Prompt.id == chat_request.prompt_id))
    prompt = result.scalars().first()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt不存在"
        )
    
    # 创建或获取会话ID（这里使用prompt_id作为会话ID的一部分）
    conversation_id = f"prompt_{chat_request.prompt_id}_{current_user.id}"
    
    # 获取用户的对话历史
    conversation_history = ensure_user_conversation_store(current_user.id, conversation_id)
    
    # 如果是新对话，添加系统提示消息（使用prompt的内容作为系统提示）
    if len(conversation_history) == 0:
        conversation_history.append({
            "role": "system",
            "content": prompt.content
        })
    
    # 添加用户消息到对话历史
    conversation_history.append({
        "role": "user",
        "content": chat_request.message
    })
    
    # 保持对话历史不超过15轮（1个系统消息 + 14轮对话 = 29条消息）
    if len(conversation_history) > 29:
        # 保留系统消息和最近的28条消息
        conversation_history = [conversation_history[0]] + conversation_history[-28:]
    
    try:
        # 调用Kimi API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                KIMI_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {KIMI_API_KEY}"
                },
                json={
                    "model": "moonshot-v1-8k",  # 使用Kimi的模型
                    "messages": conversation_history,
                    "temperature": 0.7
                },
                timeout=30.0  # 设置30秒超时
            )
            
            # 检查响应状态
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Kimi API错误: {response.text}"
                )
            
            # 解析响应
            result = response.json()
            ai_message = result["choices"][0]["message"]["content"]
            
            # 添加AI回复到对话历史
            conversation_history.append({
                "role": "assistant",
                "content": ai_message
            })
            
            # 返回回复内容和会话ID
            return {
                "response": ai_message,
                "conversation_id": conversation_id
            }
    
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"请求Kimi API时发生错误: {str(e)}"
        )

# 清除会话历史
@chat_router.delete("/chat/{conversation_id}")
async def clear_conversation(
    conversation_id: str,
    current_user: models.User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户未登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 检查会话是否存在
    if (current_user.id in user_conversations and 
        conversation_id in user_conversations[current_user.id]):
        # 删除会话
        del user_conversations[current_user.id][conversation_id]
        return {"detail": "会话已清除"}
    
    return {"detail": "会话不存在或已被清除"}
