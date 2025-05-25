import os
import json
import uuid
import aiohttp
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Dict, Optional, Any
import logging
from datetime import datetime

from . import models, schemas
from .database import get_db
from .auth import get_current_user
from .chat_service import ChatService

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建API路由
chat_router = APIRouter()

@chat_router.post("/chat", response_model=schemas.ChatResponse)
async def chat_with_prompt(
    chat_request: schemas.ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """用户与AI聊天，支持Kimi和Gemini模型"""
    # 检查用户是否已登录
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再使用聊天功能"
        )
    
    user_message = chat_request.message
    session_id = chat_request.session_id
    model = chat_request.model.lower() if chat_request.model else "kimi"  # 默认使用kimi
    
    # 验证model参数
    if model not in ["kimi", "gemini"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的模型，请选择kimi或gemini"
        )
    
    # 如果没有提供session_id，则创建新会话
    if not session_id:
        # 验证prompt_id是否存在
        if not chat_request.prompt_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="创建新会话时必须提供prompt_id"
            )
        
        prompt_id = chat_request.prompt_id
        
        # 查询prompt是否存在
        prompt_query = select(models.Prompt).filter(models.Prompt.id == prompt_id)
        prompt_result = await db.execute(prompt_query)
        prompt = prompt_result.scalars().first()
        
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt不存在"
            )
        
        # 创建新会话
        new_session_id = ChatService.create_session(
            user_id=current_user.id,
            prompt_id=prompt_id,
            prompt_content=prompt.content,
            model=model
        )
        
        # 添加用户消息
        ChatService.add_message(new_session_id, "user", user_message)
        
        # 构建API调用消息列表
        messages = ChatService.get_formatted_messages(new_session_id)
        
        # 调用相应的AI API
        if model == "kimi":
            assistant_response = await ChatService.call_kimi_api(messages)
        else:
            assistant_response = await ChatService.call_gemini_api(messages)
        
        # 保存助手回复
        ChatService.add_message(new_session_id, "assistant", assistant_response)
        
        return {
            "message": assistant_response,
            "session_id": new_session_id,
            "model": model
        }
    else:
        # 获取现有会话
        session = ChatService.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="聊天会话不存在"
            )
        
        # 验证用户是否有权限访问该会话
        if session["user_id"] != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此会话"
            )
        
        # 获取会话使用的模型
        model = session["model"]
        
        # 添加用户新消息
        ChatService.add_message(session_id, "user", user_message)
        
        # 获取格式化的消息列表
        messages = ChatService.get_formatted_messages(session_id)
        
        # 调用相应的AI API
        if model == "kimi":
            assistant_response = await ChatService.call_kimi_api(messages)
        else:
            assistant_response = await ChatService.call_gemini_api(messages)
        
        # 保存助手回复
        ChatService.add_message(session_id, "assistant", assistant_response)
        
        return {
            "message": assistant_response,
            "session_id": session_id,
            "model": model
        }

@chat_router.get("/chat/{session_id}/history", response_model=List[schemas.ChatMessage])
async def get_chat_history_api(
    session_id: str,
    current_user: models.User = Depends(get_current_user)
):
    """获取聊天历史记录"""
    # 检查用户是否已登录
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再查看聊天历史"
        )
    
    # 获取会话
    session = ChatService.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天会话不存在"
        )
    
    # 验证用户是否有权限访问该会话
    if session["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此会话"
        )
    
    # 获取消息历史，不包含system消息
    try:
        messages = ChatService.get_messages(session_id, include_system=False)
        
        # 转换为API响应格式
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg["role"],
                "content": msg["content"],
                "created_at": datetime.fromtimestamp(msg["timestamp"])
            })
        
        return formatted_messages
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@chat_router.delete("/chat/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: models.User = Depends(get_current_user)
):
    """删除聊天会话及其历史记录"""
    # 检查用户是否已登录
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再操作"
        )
    
    # 获取会话
    session = ChatService.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天会话不存在"
        )
    
    # 验证用户是否有权限删除该会话
    if session["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此会话"
        )
    
    # 删除会话
    success = ChatService.delete_session(session_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除会话失败"
        )
    
    return {"status": "success", "detail": "聊天会话已删除"}
