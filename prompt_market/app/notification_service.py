from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, delete, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime
from .models import Notification, User
from .schemas import NotificationCreate, NotificationUpdate
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    """站内信服务类"""
    
    @staticmethod
    async def create_notification(
        db: AsyncSession, 
        notification: NotificationCreate
    ) -> Notification:
        """创建站内信"""
        try:
            db_notification = Notification(**notification.dict())
            db.add(db_notification)
            await db.commit()
            await db.refresh(db_notification)
            logger.info(f"创建站内信成功: 用户{notification.user_id}, 类型{notification.notification_type}")
            return db_notification
        except Exception as e:
            await db.rollback()
            logger.error(f"创建站内信失败: {e}")
            raise
    
    @staticmethod
    async def get_user_notifications(
        db: AsyncSession,
        user_id: int,
        is_read: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Notification]:
        """获取用户的站内信列表"""
        try:
            query = select(Notification).where(Notification.user_id == user_id)
            
            if is_read is not None:
                query = query.where(Notification.is_read == is_read)
            
            query = query.order_by(Notification.created_at.desc())
            query = query.offset(offset).limit(limit)
            
            result = await db.execute(query)
            notifications = result.scalars().all()
            
            logger.info(f"获取用户{user_id}的站内信列表成功，共{len(notifications)}条")
            return list(notifications)
        except Exception as e:
            logger.error(f"获取用户站内信列表失败: {e}")
            raise
    
    @staticmethod
    async def get_notification_by_id(
        db: AsyncSession,
        notification_id: int,
        user_id: int
    ) -> Optional[Notification]:
        """根据ID获取站内信（验证用户权限）"""
        try:
            query = select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id
                )
            )
            result = await db.execute(query)
            notification = result.scalar_one_or_none()
            
            if notification:
                logger.info(f"获取站内信{notification_id}成功")
            else:
                logger.warning(f"站内信{notification_id}不存在或无权限")
            
            return notification
        except Exception as e:
            logger.error(f"获取站内信失败: {e}")
            raise
    
    @staticmethod
    async def mark_as_read(
        db: AsyncSession,
        notification_id: int,
        user_id: int
    ) -> Optional[Notification]:
        """标记站内信为已读"""
        try:
            # 先检查权限
            notification = await NotificationService.get_notification_by_id(
                db, notification_id, user_id
            )
            if not notification:
                return None
            
            # 如果已经是已读状态，直接返回
            if notification.is_read == 1:
                return notification
            
            # 更新为已读状态
            stmt = update(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id
                )
            ).values(
                is_read=1,
                read_at=datetime.utcnow()
            )
            
            await db.execute(stmt)
            await db.commit()
            
            # 重新获取更新后的数据
            await db.refresh(notification)
            
            logger.info(f"标记站内信{notification_id}为已读成功")
            return notification
        except Exception as e:
            await db.rollback()
            logger.error(f"标记站内信为已读失败: {e}")
            raise
    
    @staticmethod
    async def mark_all_as_read(
        db: AsyncSession,
        user_id: int
    ) -> int:
        """标记用户所有未读站内信为已读"""
        try:
            stmt = update(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == 0
                )
            ).values(
                is_read=1,
                read_at=datetime.utcnow()
            )
            
            result = await db.execute(stmt)
            affected_rows = result.rowcount
            await db.commit()
            
            logger.info(f"用户{user_id}标记{affected_rows}条站内信为已读")
            return affected_rows
        except Exception as e:
            await db.rollback()
            logger.error(f"批量标记已读失败: {e}")
            raise
    
    @staticmethod
    async def delete_read_notifications(
        db: AsyncSession,
        user_id: int
    ) -> int:
        """删除用户所有已读的站内信"""
        try:
            stmt = delete(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == 1
                )
            )
            
            result = await db.execute(stmt)
            affected_rows = result.rowcount
            await db.commit()
            
            logger.info(f"用户{user_id}删除{affected_rows}条已读站内信")
            return affected_rows
        except Exception as e:
            await db.rollback()
            logger.error(f"删除已读站内信失败: {e}")
            raise
    
    @staticmethod
    async def get_unread_count(
        db: AsyncSession,
        user_id: int
    ) -> int:
        """获取用户未读站内信数量"""
        try:
            query = select(func.count(Notification.id)).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == 0
                )
            )
            
            result = await db.execute(query)
            count = result.scalar()
            
            logger.info(f"用户{user_id}未读站内信数量: {count}")
            return count or 0
        except Exception as e:
            logger.error(f"获取未读数量失败: {e}")
            raise
    
    @staticmethod
    async def create_prompt_review_notification(
        db: AsyncSession,
        user_id: int,
        prompt_id: int,
        prompt_title: str,
        is_approved: bool
    ):
        """创建Prompt审核结果通知"""
        try:
            if is_approved:
                title = "Prompt审核通过"
                content = f"恭喜！您的Prompt「{prompt_title}」已通过审核，现在其他用户可以浏览和使用了。"
                notification_type = "prompt_approved"
            else:
                title = "Prompt审核未通过"
                content = f"很抱歉，您的Prompt「{prompt_title}」未通过审核。请检查内容是否符合社区规范后重新提交。"
                notification_type = "prompt_rejected"
            
            notification = NotificationCreate(
                user_id=user_id,
                title=title,
                content=content,
                notification_type=notification_type,
                related_id=prompt_id
            )
            
            return await NotificationService.create_notification(db, notification)
        except Exception as e:
            logger.error(f"创建Prompt审核通知失败: {e}")
            raise

    @staticmethod
    async def create_prompt_revert_notification(
        db: AsyncSession,
        user_id: int,
        prompt_id: int,
        prompt_title: str
    ):
        """创建Prompt撤回到待审核状态的通知"""
        try:
            title = "Prompt已撤回至待审核"
            content = f"您的Prompt「{prompt_title}」已被管理员撤回至待审核状态，需要重新审核。"
            notification_type = "prompt_reverted"
            
            notification = NotificationCreate(
                user_id=user_id,
                title=title,
                content=content,
                notification_type=notification_type,
                related_id=prompt_id
            )
            
            return await NotificationService.create_notification(db, notification)
        except Exception as e:
            logger.error(f"创建Prompt撤回通知失败: {e}")
            raise

    @staticmethod
    async def create_comment_notification(
        db: AsyncSession,
        prompt_author_id: int,
        commenter_id: int,
        commenter_username: str,
        prompt_id: int,
        prompt_title: str,
        comment_content: str
    ):
        """创建评论通知，当有用户评论Prompt时通知作者"""
        try:
            # 只有当评论者不是Prompt作者本人时才发送通知
            #if prompt_author_id == commenter_id:
                #logger.info(f"评论者是Prompt作者本人，跳过发送通知")
                #return None
            
            # 截取评论内容的前50个字符作为预览
            preview_content = comment_content[:50] + "..." if len(comment_content) > 50 else comment_content
            
            title = "收到新评论"
            content = f"用户「{commenter_username}」评论了您的Prompt「{prompt_title}」：{preview_content}"
            notification_type = "new_comment"
            
            notification = NotificationCreate(
                user_id=prompt_author_id,
                title=title,
                content=content,
                notification_type=notification_type,
                related_id=prompt_id
            )
            
            return await NotificationService.create_notification(db, notification)
        except Exception as e:
            logger.error(f"创建评论通知失败: {e}")
            raise
