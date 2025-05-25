import os
import json
import uuid
import aiohttp
from fastapi import HTTPException, status
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
import time

from .config import KIMI_API_KEY, KIMI_API_URL, GEMINI_API_KEY, GEMINI_API_URL, GEMINI_MODEL

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 默认的最大消息数量
MAX_MESSAGES = 15

# 存储用户的聊天会话（内存存储）
# 格式: {session_id: {model: str, prompt_id: int, user_id: int, messages: [messages]}}
chat_sessions = {}

class ChatService:
    @staticmethod
    def create_session(user_id: int, prompt_id: int, prompt_content: str, model: str = "kimi") -> str:
        """创建新的聊天会话"""
        session_id = str(uuid.uuid4())
        
        # 初始化会话数据
        chat_sessions[session_id] = {
            "model": model,
            "prompt_id": prompt_id,
            "user_id": user_id,
            "created_at": time.time(),
            "messages": [
                {"role": "system", "content": prompt_content, "timestamp": time.time()}
            ]
        }
        
        return session_id
        
    @staticmethod
    def get_session(session_id: str) -> Optional[Dict]:
        """获取会话数据"""
        return chat_sessions.get(session_id)
    
    @staticmethod
    def add_message(session_id: str, role: str, content: str) -> None:
        """添加消息到会话"""
        if session_id not in chat_sessions:
            raise ValueError("会话不存在")
        
        chat_sessions[session_id]["messages"].append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
    
    @staticmethod
    def get_messages(session_id: str, include_system: bool = True) -> List[Dict]:
        """获取会话中的消息"""
        if session_id not in chat_sessions:
            raise ValueError("会话不存在")
            
        messages = chat_sessions[session_id]["messages"]
        
        # 处理是否包含system消息
        if not include_system:
            return [msg for msg in messages if msg["role"] != "system"]
        
        return messages
    
    @staticmethod
    def get_formatted_messages(session_id: str) -> List[Dict]:
        """获取格式化的消息列表，用于API调用"""
        if session_id not in chat_sessions:
            raise ValueError("会话不存在")
            
        messages = chat_sessions[session_id]["messages"]
        
        # 保留最近的MAX_MESSAGES条消息
        if len(messages) > MAX_MESSAGES:
            # 始终保留第一条system消息
            system_message = next((msg for msg in messages if msg["role"] == "system"), None)
            messages = messages[-(MAX_MESSAGES-1):] # 保留最近的MAX_MESSAGES-1条
            if system_message:
                messages.insert(0, system_message)
        
        # 格式化消息
        return [{"role": msg["role"], "content": msg["content"]} for msg in messages]
    
    @staticmethod
    def delete_session(session_id: str) -> bool:
        """删除会话"""
        if session_id in chat_sessions:
            del chat_sessions[session_id]
            return True
        return False
    
    @staticmethod
    def get_user_sessions(user_id: int) -> List[Dict]:
        """获取用户的所有会话"""
        return [
            {
                "session_id": session_id,
                "prompt_id": session_data["prompt_id"],
                "model": session_data["model"],
                "created_at": session_data["created_at"]
            }
            for session_id, session_data in chat_sessions.items()
            if session_data["user_id"] == user_id
        ]

    @staticmethod
    async def call_kimi_api(messages: List[Dict]) -> str:
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
    
    @staticmethod
    async def call_gemini_api(messages: List[Dict]) -> str:
        """调用Gemini API进行对话"""
        try:
            # 将messages转换为Gemini API需要的格式
            gemini_messages = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                if msg["role"] == "system":
                    # 系统消息需要特殊处理，作为用户消息插入
                    gemini_messages.append({
                        "role": "user",
                        "parts": [{"text": f"System: {msg['content']}"}]
                    })
                    continue
                
                gemini_messages.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}]
                })
            
            model_path = f"{GEMINI_API_URL}/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "contents": gemini_messages,
                    "generationConfig": {
                        "temperature": 0.7,
                        "topP": 0.8,
                        "topK": 40
                    }
                }
                
                async with session.post(model_path, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Gemini API错误: {error_text}")
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="无法连接到Gemini AI服务"
                        )
                    
                    result = await response.json()
                    try:
                        return result["candidates"][0]["content"]["parts"][0]["text"]
                    except (KeyError, IndexError) as e:
                        logger.error(f"解析Gemini响应出错: {str(e)}, 响应: {result}")
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="解析AI响应失败"
                        )
        except Exception as e:
            logger.error(f"调用Gemini API出错: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=f"聊天处理失败: {str(e)}"
            )
