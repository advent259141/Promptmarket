# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func, desc
from typing import List, Optional

from ..models import models
from ..schemas import schemas
from ..core.database import get_db
from . import auth

# 创建通知路由
notification_router = APIRouter()

@notification_router.get("/notifications", response_model=schemas.NotificationResponse)
async def get_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    notification_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """获取当前用户的通知列表"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录"
        )
      # 构建查询条件
    query = select(models.Notification).filter(
        models.Notification.user_id == current_user.id
    ).options(
        selectinload(models.Notification.sender),
        selectinload(models.Notification.related_prompt).selectinload(models.Prompt.owner),
        selectinload(models.Notification.related_prompt).selectinload(models.Prompt.tags)
    )
    
    if notification_type:
        query = query.filter(models.Notification.notification_type == notification_type)
    
    # 计算总数
    count_query = select(func.count(models.Notification.id)).filter(
        models.Notification.user_id == current_user.id
    )
    if notification_type:
        count_query = count_query.filter(models.Notification.notification_type == notification_type)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 计算未读数量
    unread_query = select(func.count(models.Notification.id)).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == 0
    )
    if notification_type:
        unread_query = unread_query.filter(models.Notification.notification_type == notification_type)
    
    unread_result = await db.execute(unread_query)
    unread_count = unread_result.scalar()
    
    # 获取分页数据
    query = query.order_by(desc(models.Notification.created_at))
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    # 转换为响应模型
    notification_list = []
    for notification in notifications:
        notification_data = schemas.NotificationWithDetails(
            id=notification.id,
            user_id=notification.user_id,
            title=notification.title,
            content=notification.content,
            notification_type=notification.notification_type,
            is_read=notification.is_read,
            created_at=notification.created_at,
            read_at=notification.read_at,
            related_prompt_id=notification.related_prompt_id,
            sender_id=notification.sender_id,
            sender=schemas.User(
                id=notification.sender.id,
                username=notification.sender.username,
                email=notification.sender.email,
                is_admin=notification.sender.is_admin,
                oauth_provider=notification.sender.oauth_provider,
                avatar_url=notification.sender.avatar_url
            )            if notification.sender else None,              
            related_prompt=schemas.PromptList(
                id=notification.related_prompt.id,
                title=notification.related_prompt.title,
                content=notification.related_prompt.content,
                description=notification.related_prompt.description,
                user_id=notification.related_prompt.user_id,
                created_at=notification.related_prompt.created_at,
                updated_at=notification.related_prompt.updated_at,
                likes=notification.related_prompt.likes,
                dislikes=notification.related_prompt.dislikes,
                views=notification.related_prompt.views,                
                status=notification.related_prompt.status,
                is_r18=notification.related_prompt.is_r18,
                tags=[schemas.Tag(id=tag.id, name=tag.name) for tag in notification.related_prompt.tags] if notification.related_prompt.tags else [],
                owner=schemas.User(
                    id=notification.related_prompt.owner.id,
                    username=notification.related_prompt.owner.username,
                    email=notification.related_prompt.owner.email,
                    is_admin=notification.related_prompt.owner.is_admin,
                    oauth_provider=notification.related_prompt.owner.oauth_provider,
                    avatar_url=notification.related_prompt.owner.avatar_url
                )
            ) if notification.related_prompt else None
        )
        notification_list.append(notification_data)
    
    return schemas.NotificationResponse(
        notifications=notification_list,
        total=total,
        unread_count=unread_count
    )

@notification_router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """标记通知为已读"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录"
        )
    
    # 查找通知
    result = await db.execute(
        select(models.Notification).filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == current_user.id
        )
    )
    notification = result.scalars().first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知不存在"
        )
    
    # 标记为已读
    if notification.is_read == 0:
        notification.is_read = 1
        notification.read_at = func.now()
        await db.commit()
    
    return {"message": "通知已标记为已读"}

@notification_router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(
    notification_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """标记所有通知为已读"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录"
        )
    
    # 构建更新条件
    update_query = models.Notification.__table__.update().where(
        (models.Notification.user_id == current_user.id) &
        (models.Notification.is_read == 0)
    )
    
    if notification_type:
        update_query = update_query.where(
            models.Notification.notification_type == notification_type
        )
    
    # 执行更新
    await db.execute(
        update_query.values(
            is_read=1,
            read_at=func.now()
        )
    )
    await db.commit()
    
    return {"message": "所有通知已标记为已读"}

@notification_router.get("/notifications/unread-count")
async def get_notification_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """获取当前用户的未读通知数量"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录"
        )
    
    result = await db.execute(
        select(func.count(models.Notification.id)).filter(
            models.Notification.user_id == current_user.id,
            models.Notification.is_read == 0
        )
    )
    unread_count = result.scalar()
    
    return {"unread_count": unread_count}

@notification_router.post("/admin/send-notification", response_model=dict)
async def send_admin_notification(
    notification_data: schemas.SendNotificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """管理员发送通知给指定用户"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录"
        )
    
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以发送通知"
        )
    
    # 验证用户ID是否存在
    user_check_result = await db.execute(
        select(models.User.id).filter(
            models.User.id.in_(notification_data.user_ids)
        )
    )
    existing_user_ids = [row[0] for row in user_check_result.fetchall()]
    
    if len(existing_user_ids) != len(notification_data.user_ids):
        missing_ids = set(notification_data.user_ids) - set(existing_user_ids)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"用户ID不存在: {list(missing_ids)}"
        )
    
    # 创建通知
    notifications = []
    for user_id in notification_data.user_ids:
        notification = models.Notification(
            user_id=user_id,
            title=notification_data.title,
            content=notification_data.content,
            notification_type=notification_data.notification_type,
            sender_id=current_user.id,
            is_read=0
        )
        notifications.append(notification)
    
    db.add_all(notifications)
    await db.commit()
    
    return {
        "message": f"成功发送通知给 {len(notification_data.user_ids)} 个用户",
        "sent_count": len(notification_data.user_ids)
    }

# 系统自动创建通知的函数
async def create_system_notification(
    db: AsyncSession,
    user_id: int,
    title: str,
    content: str,
    notification_type: str,
    related_prompt_id: Optional[int] = None
):
    """创建系统通知"""
    notification = models.Notification(
        user_id=user_id,
        title=title,
        content=content,
        notification_type=notification_type,
        related_prompt_id=related_prompt_id,
        is_read=0
    )
    db.add(notification)
    await db.flush()  # 获取ID但不提交
    return notification