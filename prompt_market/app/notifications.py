from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from .database import get_db
from .auth import get_current_user
from .models import User
from .schemas import Notification, NotificationCreate, NotificationUpdate
from .notification_service import NotificationService
import logging

logger = logging.getLogger(__name__)
notifications_router = APIRouter()

@notifications_router.get("/notifications", response_model=List[Notification])
async def get_notifications(
    is_read: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的站内信列表"""
    try:
        notifications = await NotificationService.get_user_notifications(
            db=db,
            user_id=current_user.id,
            is_read=is_read,
            limit=limit,
            offset=offset
        )
        return notifications
    except Exception as e:
        logger.error(f"获取站内信列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取站内信列表失败"
        )

@notifications_router.get("/notifications/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取未读站内信数量"""
    try:
        count = await NotificationService.get_unread_count(
            db=db,
            user_id=current_user.id
        )
        return {"unread_count": count}
    except Exception as e:
        logger.error(f"获取未读数量失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取未读数量失败"
        )

@notifications_router.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """标记单个站内信为已读"""
    try:
        notification = await NotificationService.mark_as_read(
            db=db,
            notification_id=notification_id,
            user_id=current_user.id
        )
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="站内信不存在或无权限访问"
            )
        
        return {"message": "已标记为已读", "notification": notification}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"标记已读失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="标记已读失败"
        )

@notifications_router.put("/notifications/mark-all-read")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """标记所有站内信为已读"""
    try:
        affected_count = await NotificationService.mark_all_as_read(
            db=db,
            user_id=current_user.id
        )
        
        return {
            "message": f"已标记{affected_count}条站内信为已读",
            "affected_count": affected_count
        }
    except Exception as e:
        logger.error(f"批量标记已读失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="批量标记已读失败"
        )

@notifications_router.delete("/notifications/delete-read")
async def delete_read_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除所有已读的站内信"""
    try:
        deleted_count = await NotificationService.delete_read_notifications(
            db=db,
            user_id=current_user.id
        )
        
        return {
            "message": f"已删除{deleted_count}条已读站内信",
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"删除已读站内信失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除已读站内信失败"
        )

@notifications_router.get("/notifications/{notification_id}", response_model=Notification)
async def get_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取单个站内信详情"""
    try:
        notification = await NotificationService.get_notification_by_id(
            db=db,
            notification_id=notification_id,
            user_id=current_user.id
        )
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="站内信不存在或无权限访问"
            )
        
        return notification
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取站内信详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取站内信详情失败"
        )
