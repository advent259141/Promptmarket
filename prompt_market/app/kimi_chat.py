import os
import json
import uuid
import aiohttp
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from typing import List, Optional
import logging

from . import models, schemas
from .database import get_db
from .auth import get_current_user

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建API路由
chat_router = APIRouter()

# Kimi API配置
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
KIMI_API_URL = "https://api.moonshot.cn/v1/chat/completions"

# 默认的最大消息数量
MAX_MESSAGES = 15

async def call_kimi_api(messages):
    """调用Kimi API进行对话"""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {KIMI_API_KEY}"
            }
            
            payload = {
                "model": "moonshot-v1-8k",
                "messages": messages,
                "temperature": 0.7,
                "stream": False
            }
            
            async with session.post(KIMI_API_URL, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Kimi API错误: {error_text}")
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="无法连接到Kimi AI服务"
                    )
                
                result = await response.json()
                return result["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"调用Kimi API出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"聊天处理失败: {str(e)}"
        )

async def get_chat_history(session_id: str, db: AsyncSession):
    """获取聊天历史记录"""
    # 查询会话
    session_query = select(models.ChatSession).filter(models.ChatSession.session_id == session_id)
    session_result = await db.execute(session_query)
    chat_session = session_result.scalars().first()
    
    if not chat_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天会话不存在"
        )
    
    # 查询消息历史
    message_query = select(models.ChatMessage).filter(
        models.ChatMessage.session_id == chat_session.id
    ).order_by(models.ChatMessage.created_at.asc())
    
    message_result = await db.execute(message_query)
    messages = message_result.scalars().all()
    
    # 构建消息格式
    message_list = [
        {"role": msg.role, "content": msg.content} for msg in messages
    ]
    
    return message_list, chat_session

@chat_router.post("/chat", response_model=schemas.ChatResponse)
async def chat_with_prompt(
    chat_request: schemas.ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """用户与使用特定prompt作为system prompt的AI聊天"""
    # 检查用户是否已登录
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再使用聊天功能"
        )
    
    user_message = chat_request.message
    session_id = chat_request.session_id
    
    # 如果没有提供session_id，则创建新会话
    if not session_id:
        # 验证prompt_id是否存在
        if "prompt_id" not in chat_request.model_dump():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="创建新会话时必须提供prompt_id"
            )
        
        prompt_id = chat_request.model_dump()["prompt_id"]
        
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
        new_session_id = str(uuid.uuid4())
        new_session = models.ChatSession(
            session_id=new_session_id,
            prompt_id=prompt_id,
            user_id=current_user.id
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        
        # 添加system消息
        system_message = models.ChatMessage(
            session_id=new_session.id,
            role="system",
            content=prompt.content
        )
        db.add(system_message)
        await db.commit()
        
        # 添加用户消息
        user_msg = models.ChatMessage(
            session_id=new_session.id,
            role="user",
            content=user_message
        )
        db.add(user_msg)
        await db.commit()
        
        # 构建调用Kimi的消息列表
        messages = [
            {"role": "system", "content": prompt.content},
            {"role": "user", "content": user_message}
        ]
        
        # 调用Kimi API
        assistant_response = await call_kimi_api(messages)
        
        # 保存助手回复
        assistant_msg = models.ChatMessage(
            session_id=new_session.id,
            role="assistant",
            content=assistant_response
        )
        db.add(assistant_msg)
        await db.commit()
        
        return {
            "message": assistant_response,
            "session_id": new_session_id
        }
    else:
        # 获取现有会话的历史记录
        message_list, chat_session = await get_chat_history(session_id, db)
        
        # 添加用户新消息
        user_msg = models.ChatMessage(
            session_id=chat_session.id,
            role="user",
            content=user_message
        )
        db.add(user_msg)
        await db.commit()
        
        # 更新消息列表，保留最近MAX_MESSAGES条消息
        message_list.append({"role": "user", "content": user_message})
        if len(message_list) > MAX_MESSAGES:
            # 始终保留system消息
            system_message = next((msg for msg in message_list if msg["role"] == "system"), None)
            message_list = message_list[-(MAX_MESSAGES-1):] # 保留最近的MAX_MESSAGES-1条
            if system_message:
                message_list.insert(0, system_message)
        
        # 调用Kimi API
        assistant_response = await call_kimi_api(message_list)
        
        # 保存助手回复
        assistant_msg = models.ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            content=assistant_response
        )
        db.add(assistant_msg)
        await db.commit()
        
        return {
            "message": assistant_response,
            "session_id": session_id
        }

@chat_router.get("/chat/{session_id}/history", response_model=List[schemas.ChatMessage])
async def get_chat_history_api(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """获取聊天历史记录"""
    # 检查用户是否已登录
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再查看聊天历史"
        )
    
    # 查询会话
    session_query = select(models.ChatSession).filter(
        models.ChatSession.session_id == session_id,
        models.ChatSession.user_id == current_user.id
    )
    session_result = await db.execute(session_query)
    chat_session = session_result.scalars().first()
    
    if not chat_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天会话不存在或无权访问"
        )
    
    # 查询消息历史，不包含system消息
    message_query = select(models.ChatMessage).filter(
        models.ChatMessage.session_id == chat_session.id,
        models.ChatMessage.role != "system"
    ).order_by(models.ChatMessage.created_at.asc())
    
    message_result = await db.execute(message_query)
    messages = message_result.scalars().all()
    
    return messages

@chat_router.delete("/chat/{session_id}")
async def delete_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """删除聊天会话及其历史记录"""
    # 检查用户是否已登录
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再操作"
        )
    
    # 查询会话
    session_query = select(models.ChatSession).filter(
        models.ChatSession.session_id == session_id,
        models.ChatSession.user_id == current_user.id
    )
    session_result = await db.execute(session_query)
    chat_session = session_result.scalars().first()
    
    if not chat_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天会话不存在或无权删除"
        )
    
    # 删除相关消息
    await db.execute(f"DELETE FROM chat_messages WHERE session_id = {chat_session.id}")
    
    # 删除会话
    await db.delete(chat_session)
    await db.commit()
    
    return {"status": "success", "detail": "聊天会话已删除"} 