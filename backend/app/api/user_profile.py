# -*- coding: utf-8 -*-
"""
用户主页相关的API路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func, and_, or_
from typing import List, Optional

from ..models import models
from ..schemas import schemas
from ..core.database import get_db
from .auth import get_current_user

# 创建路由
user_profile_router = APIRouter()

@user_profile_router.get("/user/{user_id}/profile", response_model=schemas.UserProfileWithFollow)
async def get_user_profile(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """获取用户主页信息，包含关注状态"""
    # 查询用户信息
    user_query = select(models.User).filter(models.User.id == user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 查询关注状态和统计
    is_following = False
    followers_count = 0
    following_count = 0
    
    if current_user:
        # 检查当前用户是否关注了该用户
        follow_check_query = select(models.user_follow).where(
            and_(
                models.user_follow.c.follower_id == current_user.id,
                models.user_follow.c.following_id == user_id
            )
        )
        follow_result = await db.execute(follow_check_query)
        is_following = follow_result.first() is not None
    
    # 统计粉丝数
    followers_query = select(func.count()).select_from(models.user_follow).where(
        models.user_follow.c.following_id == user_id
    )
    followers_result = await db.execute(followers_query)
    followers_count = followers_result.scalar() or 0
    
    # 统计关注数
    following_query = select(func.count()).select_from(models.user_follow).where(
        models.user_follow.c.follower_id == user_id
    )
    following_result = await db.execute(following_query)
    following_count = following_result.scalar() or 0

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
        },
        "is_following": is_following,
        "followers_count": followers_count,
        "following_count": following_count
    }

@user_profile_router.post("/user/{user_id}/follow", response_model=schemas.FollowResponse)
async def follow_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """关注用户"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录"
        )
    
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能关注自己"
        )
    
    # 检查要关注的用户是否存在
    target_user_query = select(models.User).filter(models.User.id == user_id)
    target_user_result = await db.execute(target_user_query)
    target_user = target_user_result.scalars().first()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 检查是否已经关注
    existing_follow_query = select(models.user_follow).where(
        and_(
            models.user_follow.c.follower_id == current_user.id,
            models.user_follow.c.following_id == user_id
        )
    )
    existing_follow_result = await db.execute(existing_follow_query)
    
    if existing_follow_result.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已经关注了该用户"
        )
    
    # 创建关注关系
    follow_stmt = models.user_follow.insert().values(
        follower_id=current_user.id,
        following_id=user_id
    )
    await db.execute(follow_stmt)
    await db.commit()
    
    return {
        "message": "关注成功",
        "is_following": True
    }

@user_profile_router.delete("/user/{user_id}/follow", response_model=schemas.FollowResponse)
async def unfollow_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """取消关注用户"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录"
        )
    
    # 检查关注关系是否存在
    existing_follow_query = select(models.user_follow).where(
        and_(
            models.user_follow.c.follower_id == current_user.id,
            models.user_follow.c.following_id == user_id
        )
    )
    existing_follow_result = await db.execute(existing_follow_query)
    
    if not existing_follow_result.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未关注该用户"
        )
    
    # 删除关注关系
    unfollow_stmt = models.user_follow.delete().where(
        and_(
            models.user_follow.c.follower_id == current_user.id,
            models.user_follow.c.following_id == user_id
        )
    )
    await db.execute(unfollow_stmt)
    await db.commit()
    
    return {
        "message": "取消关注成功",
        "is_following": False
    }

@user_profile_router.get("/user/{user_id}/following", response_model=schemas.FollowListResponse)
async def get_user_following(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_current_user)
):
    """获取用户关注的人列表"""
    # 检查用户是否存在
    user_query = select(models.User).filter(models.User.id == user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 查询关注列表
    following_query = select(models.User).join(
        models.user_follow,
        models.User.id == models.user_follow.c.following_id
    ).filter(
        models.user_follow.c.follower_id == user_id
    ).order_by(models.user_follow.c.created_at.desc())
    
    following_result = await db.execute(following_query)
    following_users = following_result.scalars().all()
    
    # 如果有当前用户，检查当前用户对这些人的关注状态
    users_with_follow_status = []
    for followed_user in following_users:
        is_following = False
        if current_user and current_user.id != followed_user.id:
            follow_check_query = select(models.user_follow).where(
                and_(
                    models.user_follow.c.follower_id == current_user.id,
                    models.user_follow.c.following_id == followed_user.id
                )
            )
            follow_result = await db.execute(follow_check_query)
            is_following = follow_result.first() is not None
        
        users_with_follow_status.append({
            "user": followed_user,
            "is_following": is_following
        })
    
    return {
        "users": users_with_follow_status,
        "total": len(following_users)
    }

@user_profile_router.get("/user/{user_id}/followers", response_model=schemas.FollowListResponse)
async def get_user_followers(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_current_user)
):
    """获取用户的粉丝列表"""
    # 检查用户是否存在
    user_query = select(models.User).filter(models.User.id == user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 查询粉丝列表
    followers_query = select(models.User).join(
        models.user_follow,
        models.User.id == models.user_follow.c.follower_id
    ).filter(
        models.user_follow.c.following_id == user_id
    ).order_by(models.user_follow.c.created_at.desc())
    
    followers_result = await db.execute(followers_query)
    follower_users = followers_result.scalars().all()
    
    # 如果有当前用户，检查当前用户对这些人的关注状态
    users_with_follow_status = []
    for follower_user in follower_users:
        is_following = False
        if current_user and current_user.id != follower_user.id:
            follow_check_query = select(models.user_follow).where(
                and_(
                    models.user_follow.c.follower_id == current_user.id,
                    models.user_follow.c.following_id == follower_user.id
                )
            )
            follow_result = await db.execute(follow_check_query)
            is_following = follow_result.first() is not None
        
        users_with_follow_status.append({
            "user": follower_user,
            "is_following": is_following
        })
    
    return {
        "users": users_with_follow_status,
        "total": len(follower_users)
    }

@user_profile_router.get("/user/{user_id}/comments")
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

@user_profile_router.get("/user/{user_id}/can-message")
async def can_send_message_to_user(
    user_id: int,
    current_user: models.User = Depends(get_current_user)
):
    """检查当前用户是否可以给指定用户发送私信"""
    # 必须登录才能发送私信
    if not current_user:
        return {"can_message": False, "reason": "需要登录"}
    
    # 不能给自己发私信
    if current_user.id == user_id:
        return {"can_message": False, "reason": "不能给自己发送私信"}
    
    # 其他情况都可以发送私信
    return {"can_message": True}
