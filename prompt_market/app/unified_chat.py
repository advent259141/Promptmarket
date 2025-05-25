import os
import json
import uuid
import aiohttp
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
import google.generativeai as genai

from . import models, schemas
from .database import get_db
from .auth import get_current_user

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建API路由
unified_chat_router = APIRouter()

# API配置
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
KIMI_API_URL = "https://api.moonshot.cn/v1/chat/completions"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

# 默认的最大消息数量
MAX_MESSAGES = 15

# 内存存储对话历史
# 格式: {session_id: {"messages": [...], "prompt_id": int, "user_id": int, "model_type": str, "created_at": datetime}}
memory_conversations: Dict[str, Dict[str, Any]] = {}

def cleanup_old_conversations():
    """清理超过24小时的对话"""
    current_time = datetime.now()
    old_sessions = []
    
    for session_id, conversation in memory_conversations.items():
        created_at = conversation.get("created_at", current_time)
        if (current_time - created_at).total_seconds() > 86400:  # 24小时
            old_sessions.append(session_id)
    
    for session_id in old_sessions:
        del memory_conversations[session_id]
        logger.info(f"清理过期对话会话: {session_id}")

async def call_kimi_api(messages: List[Dict[str, str]]) -> str:
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
            detail=f"Kimi聊天处理失败: {str(e)}"
        )

async def call_gemini_api(messages: List[Dict[str, str]]) -> str:
    """调用Gemini API进行对话"""
    try:
        if not GEMINI_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Gemini API密钥未配置"
            )
        
        # 配置Gemini API
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        
        # 将消息格式转换为Gemini格式
        gemini_messages = []
        system_instruction = ""
        
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                gemini_messages.append({
                    "role": "user",
                    "parts": [msg["content"]]
                })
            elif msg["role"] == "assistant":
                gemini_messages.append({
                    "role": "model",
                    "parts": [msg["content"]]
                })
        
        # 重新配置模型，如果有系统指令的话
        if system_instruction:
            model = genai.GenerativeModel(
                model_name=GEMINI_MODEL,
                system_instruction=system_instruction
            )
        
        # 如果没有对话历史，直接发送消息
        if len(gemini_messages) <= 1:
            if gemini_messages:
                response = model.generate_content(gemini_messages[0]["parts"][0])
                return response.text
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="没有有效的消息内容"
                )
        
        # 如果有对话历史，使用chat功能
        # 获取历史消息（除了最后一条）
        history = gemini_messages[:-1]
        chat = model.start_chat(history=history)
        
        # 发送最后一条消息
        last_message = gemini_messages[-1]["parts"][0]
        response = chat.send_message(last_message)
        return response.text
    
    except Exception as e:
        logger.error(f"调用Gemini API出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Gemini聊天处理失败: {str(e)}"
        )

@unified_chat_router.post("/unified-chat", response_model=schemas.ChatResponse)
async def unified_chat(
    chat_request: schemas.ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """统一聊天接口，支持kimi和gemini模型选择"""
    # 检查用户是否已登录
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再使用聊天功能"
        )
    
    # 清理过期对话
    cleanup_old_conversations()
    
    user_message = chat_request.message
    session_id = chat_request.session_id
    model_type = chat_request.model_type or "gemini"
    
    # 验证模型类型
    if model_type not in ["kimi", "gemini"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的模型类型，请选择 'kimi' 或 'gemini'"
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
        
        # 创建新会话ID
        session_id = str(uuid.uuid4())
        
        # 初始化对话历史
        messages = [
            {"role": "system", "content": prompt.content},
            {"role": "user", "content": user_message}
        ]
        
        # 存储到内存
        memory_conversations[session_id] = {
            "messages": messages,
            "prompt_id": prompt_id,
            "user_id": current_user.id,
            "model_type": model_type,
            "created_at": datetime.now()
        }
        
        # 调用相应的AI API
        if model_type == "kimi":
            if not KIMI_API_KEY:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Kimi API密钥未配置"
                )
            assistant_response = await call_kimi_api(messages)
        else:  # gemini
            assistant_response = await call_gemini_api(messages)
        
        # 添加助手回复到对话历史
        memory_conversations[session_id]["messages"].append({
            "role": "assistant", 
            "content": assistant_response
        })
        
        return {
            "message": assistant_response,
            "session_id": session_id,
            "model_type": model_type
        }
    
    else:
        # 获取现有会话
        if session_id not in memory_conversations:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="聊天会话不存在或已过期"
            )
        
        conversation = memory_conversations[session_id]
        
        # 验证用户权限
        if conversation["user_id"] != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此聊天会话"
            )
        
        # 获取当前会话的模型类型
        session_model_type = conversation["model_type"]
        
        # 添加用户新消息
        conversation["messages"].append({"role": "user", "content": user_message})
        
        # 保持消息数量在限制内
        messages = conversation["messages"]
        if len(messages) > MAX_MESSAGES:
            # 始终保留system消息
            system_message = next((msg for msg in messages if msg["role"] == "system"), None)
            messages = messages[-(MAX_MESSAGES-1):]  # 保留最近的MAX_MESSAGES-1条
            if system_message:
                messages.insert(0, system_message)
            conversation["messages"] = messages
        
        # 调用相应的AI API
        if session_model_type == "kimi":
            if not KIMI_API_KEY:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Kimi API密钥未配置"
                )
            assistant_response = await call_kimi_api(messages)
        else:  # gemini
            assistant_response = await call_gemini_api(messages)
        
        # 添加助手回复到对话历史
        conversation["messages"].append({
            "role": "assistant", 
            "content": assistant_response
        })
        
        return {
            "message": assistant_response,
            "session_id": session_id,
            "model_type": session_model_type
        }

@unified_chat_router.get("/unified-chat/{session_id}/history", response_model=List[schemas.ChatMessage])
async def get_unified_chat_history(
    session_id: str,
    current_user: models.User = Depends(get_current_user)
):
    """获取统一聊天历史记录"""
    # 检查用户是否已登录
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再查看聊天历史"
        )
    
    # 清理过期对话
    cleanup_old_conversations()
    
    # 检查会话是否存在
    if session_id not in memory_conversations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天会话不存在或已过期"
        )
    
    conversation = memory_conversations[session_id]
    
    # 验证用户权限
    if conversation["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此聊天会话"
        )
    
    # 返回消息历史，不包含system消息
    messages = [
        {
            "role": msg["role"],
            "content": msg["content"],
            "timestamp": datetime.now()
        }
        for msg in conversation["messages"]
        if msg["role"] != "system"
    ]
    
    return messages

@unified_chat_router.delete("/unified-chat/{session_id}")
async def delete_unified_chat_session(
    session_id: str,
    current_user: models.User = Depends(get_current_user)
):
    """删除统一聊天会话"""
    # 检查用户是否已登录
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录后再操作"
        )
    
    # 检查会话是否存在
    if session_id not in memory_conversations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天会话不存在或已过期"
        )
    
    conversation = memory_conversations[session_id]
    
    # 验证用户权限
    if conversation["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此聊天会话"
        )
    
    # 删除会话
    del memory_conversations[session_id]
    
    return {"status": "success", "detail": "聊天会话已删除"}

@unified_chat_router.get("/chat-models")
async def get_available_models():
    """获取可用的聊天模型"""
    models = []
    
    if KIMI_API_KEY:
        models.append({
            "type": "kimi",
            "name": "Kimi (moonshot-v1-8k)",
            "description": "Moonshot AI 的 Kimi 模型"
        })
    
    if GEMINI_API_KEY:
        models.append({
            "type": "gemini",
            "name": f"Gemini ({GEMINI_MODEL})",
            "description": "Google 的 Gemini 模型"
        })
    
    return {"models": models} 