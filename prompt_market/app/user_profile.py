# -*- coding: utf-8 -*-
"""
用户主页相关的API路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional

from . import models, schemas
from .database import get_db
from .auth import get_current_user

# 创建路由
user_profile_router = APIRouter()

@user_profile_router.get("/user/{user_id}/profile", response_model=schemas.UserProfile)
async def get_user_profile(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """获取用户主页信息"""
    # 查询用户信息
    user_query = select(models.User).filter(models.User.id == user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
      # 查询用户的prompts
    # 如果是查看自己的资料，显示所有状态的Prompt；否则只显示已通过审核的
    if current_user and current_user.id == user_id:
        # 用户查看自己的资料，显示所有状态的Prompt
        prompts_query = select(models.Prompt).options(
            selectinload(models.Prompt.tags),
            selectinload(models.Prompt.owner)
        ).filter(
            models.Prompt.user_id == user_id
        ).order_by(models.Prompt.created_at.desc())
    else:
        # 其他用户查看，只显示已通过审核的
        prompts_query = select(models.Prompt).options(
            selectinload(models.Prompt.tags),
            selectinload(models.Prompt.owner)
        ).filter(
            models.Prompt.user_id == user_id,
            models.Prompt.status == 1  # 只显示已通过审核的
        ).order_by(models.Prompt.created_at.desc())
    
    prompts_result = await db.execute(prompts_query)
    prompts = prompts_result.scalars().all()
    
    # 统计数据
    total_prompts = len(prompts)
    total_likes = sum(prompt.likes for prompt in prompts)
    total_views = sum(prompt.views for prompt in prompts)
    
    return {
        "user": user,
        "prompts": prompts,
        "stats": {
            "total_prompts": total_prompts,
            "total_likes": total_likes,
            "total_views": total_views
        }
    }

@user_profile_router.get("/user/{username}/profile-by-username", response_model=schemas.UserProfile)
async def get_user_profile_by_username(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """通过用户名获取用户主页信息"""
    # 查询用户信息
    user_query = select(models.User).filter(models.User.username == username)
    user_result = await db.execute(user_query)
    user = user_result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 重用现有的逻辑
    return await get_user_profile(user.id, db, current_user)

@user_profile_router.get("/users/{user_id}/comments")
async def get_user_comments(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """获取用户发表的评论列表"""
    # 验证用户是否存在
    user_query = select(models.User).filter(models.User.id == user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 查询用户的评论，包含对应的Prompt标题
    comments_query = select(models.Comment, models.Prompt.title.label('prompt_title')).join(
        models.Prompt, models.Comment.prompt_id == models.Prompt.id
    ).filter(
        models.Comment.user_id == user_id
    ).order_by(models.Comment.created_at.desc())
    
    comments_result = await db.execute(comments_query)
    comments_data = comments_result.all()
      # 格式化评论数据
    comments = []
    for comment, prompt_title in comments_data:
        comments.append({
            "id": comment.id,
            "content": comment.content,
            "created_at": comment.created_at,
            "likes": getattr(comment, 'likes', 0),  # 如果字段不存在则默认为0
            "dislikes": getattr(comment, 'dislikes', 0),  # 如果字段不存在则默认为0
            "prompt_id": comment.prompt_id,
            "prompt_title": prompt_title
        })
    
    return comments
