from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import or_, func
from typing import List

from ..models import models
from ..schemas import schemas
from ..core.database import get_db
from . import auth

# 创建私信路由
private_message_router = APIRouter()

@private_message_router.post("/send", response_model=schemas.PrivateMessageWithUser, status_code=status.HTTP_201_CREATED)
async def send_private_message(
    message_data: schemas.SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """发送私信"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录"
        )
    
    # 检查接收者是否存在
    result = await db.execute(select(models.User).filter(models.User.id == message_data.receiver_id))
    receiver = result.scalars().first()
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="接收者不存在"
        )
    
    # 不能给自己发消息
    if current_user.id == message_data.receiver_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能给自己发送私信"
        )
    
    # 创建或更新消息会话
    user1_id = min(current_user.id, message_data.receiver_id)
    user2_id = max(current_user.id, message_data.receiver_id)
    
    # 查询是否已存在会话
    thread_result = await db.execute(
        select(models.MessageThread).filter(
            models.MessageThread.user1_id == user1_id,
            models.MessageThread.user2_id == user2_id
        )
    )
    thread = thread_result.scalars().first()
    
    if not thread:
        # 创建新会话
        thread = models.MessageThread(
            user1_id=user1_id,
            user2_id=user2_id,
            user1_unread_count=0,
            user2_unread_count=0
        )
        db.add(thread)
        await db.flush()  # 获取thread.id
      # 创建私信
    private_message = models.PrivateMessage(
        sender_id=current_user.id,
        receiver_id=message_data.receiver_id,
        content=message_data.content,
        is_read=0
    )
    db.add(private_message)
    
    # 更新会话的未读计数和最后消息时间
    thread.last_message_at = func.now()
    if current_user.id == user1_id:
        thread.user2_unread_count += 1
    else:
        thread.user1_unread_count += 1
    
    # 刷新以获取ID，但不提交
    await db.flush()
    message_id = private_message.id
    
    await db.commit()
    
    # 重新查询消息以获取关联数据
    result = await db.execute(
        select(models.PrivateMessage)
        .options(selectinload(models.PrivateMessage.sender), selectinload(models.PrivateMessage.receiver))
        .filter(models.PrivateMessage.id == message_id)
    )
    private_message = result.scalars().first()
      # 构造返回的消息数据
    message_response = schemas.PrivateMessageWithUser(
        id=private_message.id,
        content=private_message.content,
        sender_id=private_message.sender_id,
        receiver_id=private_message.receiver_id,
        created_at=private_message.created_at,
        is_read=private_message.is_read,
        sender=schemas.User(
            id=private_message.sender.id,
            username=private_message.sender.username,
            email=private_message.sender.email,
            is_admin=private_message.sender.is_admin,
            oauth_provider=private_message.sender.oauth_provider,
            avatar_url=private_message.sender.avatar_url
        ),
        receiver=schemas.User(
            id=private_message.receiver.id,
            username=private_message.receiver.username,
            email=private_message.receiver.email,
            is_admin=private_message.receiver.is_admin,
            oauth_provider=private_message.receiver.oauth_provider,
            avatar_url=private_message.receiver.avatar_url
        )
    )
    
    return message_response

@private_message_router.get("/conversations", response_model=List[schemas.ConversationResponse])
async def get_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """获取当前用户的所有对话列表"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录"
        )
      # 查询当前用户参与的所有会话
    result = await db.execute(
        select(models.MessageThread)
        .options(selectinload(models.MessageThread.user1), selectinload(models.MessageThread.user2))
        .filter(
            or_(
                models.MessageThread.user1_id == current_user.id,
                models.MessageThread.user2_id == current_user.id
            )
        )
        .order_by(models.MessageThread.last_message_at.desc())
    )
    threads = result.scalars().all()
    conversations = []
    for thread in threads:
        # 确定对方用户
        other_user = thread.user2 if thread.user1_id == current_user.id else thread.user1
        
        # 确定未读数量
        unread_count = (
            thread.user1_unread_count if thread.user1_id == current_user.id 
            else thread.user2_unread_count
        )
        
        # 获取最新消息
        latest_msg_result = await db.execute(
            select(models.PrivateMessage)
            .filter(
                or_(
                    (models.PrivateMessage.sender_id == current_user.id) & 
                    (models.PrivateMessage.receiver_id == other_user.id),
                    (models.PrivateMessage.sender_id == other_user.id) & 
                    (models.PrivateMessage.receiver_id == current_user.id)
                )
            )
            .order_by(models.PrivateMessage.created_at.desc())
            .limit(1)
        )
        latest_message = latest_msg_result.scalars().first()
          # 构造对话响应数据
        conversation = schemas.ConversationResponse(
            thread_id=thread.id,
            other_user=schemas.User(
                id=other_user.id,
                username=other_user.username,
                email=other_user.email,
                is_admin=other_user.is_admin,
                oauth_provider=other_user.oauth_provider,
                avatar_url=other_user.avatar_url
            ),
            last_message_at=thread.last_message_at,
            unread_count=unread_count,
            latest_message=latest_message.content if latest_message else None
        )
        conversations.append(conversation)
    
    return conversations

@private_message_router.get("/conversation/{user_id}", response_model=List[schemas.PrivateMessageWithUser])
async def get_conversation_messages(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """获取与指定用户的对话消息"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录"
        )
    
    # 检查对方用户是否存在
    result = await db.execute(select(models.User).filter(models.User.id == user_id))
    other_user = result.scalars().first()
    if not other_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )    # 查询两人之间的所有消息
    messages_result = await db.execute(
        select(models.PrivateMessage)
        .options(selectinload(models.PrivateMessage.sender), selectinload(models.PrivateMessage.receiver))
        .filter(
            or_(
                (models.PrivateMessage.sender_id == current_user.id) & 
                (models.PrivateMessage.receiver_id == user_id),
                (models.PrivateMessage.sender_id == user_id) & 
                (models.PrivateMessage.receiver_id == current_user.id)
            )
        )
        .order_by(models.PrivateMessage.created_at.asc())
    )
    messages = messages_result.scalars().all()
      # 将ORM对象转换为Pydantic模型
    message_list = []
    for msg in messages:
        message_data = schemas.PrivateMessageWithUser(
            id=msg.id,
            content=msg.content,
            sender_id=msg.sender_id,
            receiver_id=msg.receiver_id,
            created_at=msg.created_at,
            is_read=msg.is_read,
            sender=schemas.User(
                id=msg.sender.id,
                username=msg.sender.username,
                email=msg.sender.email,
                is_admin=msg.sender.is_admin,
                oauth_provider=msg.sender.oauth_provider,
                avatar_url=msg.sender.avatar_url
            ),
            receiver=schemas.User(
                id=msg.receiver.id,
                username=msg.receiver.username,
                email=msg.receiver.email,
                is_admin=msg.receiver.is_admin,
                oauth_provider=msg.receiver.oauth_provider,
                avatar_url=msg.receiver.avatar_url
            )
        )
        message_list.append(message_data)
    
    # 标记接收的消息为已读
    await db.execute(
        models.PrivateMessage.__table__.update()
        .where(
            (models.PrivateMessage.sender_id == user_id) &
            (models.PrivateMessage.receiver_id == current_user.id) &
            (models.PrivateMessage.is_read == 0)
        )
        .values(is_read=1)
    )
    
    # 更新会话的未读计数
    user1_id = min(current_user.id, user_id)
    user2_id = max(current_user.id, user_id)
    
    thread_result = await db.execute(
        select(models.MessageThread).filter(
            models.MessageThread.user1_id == user1_id,
            models.MessageThread.user2_id == user2_id
        )
    )
    thread = thread_result.scalars().first()
    
    if thread:
        if current_user.id == user1_id:
            thread.user1_unread_count = 0
        else:
            thread.user2_unread_count = 0
    
    await db.commit()
    
    return message_list

@private_message_router.get("/unread-count")
async def get_unread_message_count(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """获取当前用户的未读消息总数"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录"
        )
    
    # 查询当前用户参与的所有会话并计算未读消息数
    thread_result = await db.execute(
        select(models.MessageThread)
        .filter(
            or_(
                models.MessageThread.user1_id == current_user.id,
                models.MessageThread.user2_id == current_user.id
            )
        )
    )
    threads = thread_result.scalars().all()
    
    user_unread_count = 0
    for thread in threads:
        if thread.user1_id == current_user.id:
            user_unread_count += thread.user1_unread_count
        else:
            user_unread_count += thread.user2_unread_count
    
    return {"unread_count": user_unread_count}

@private_message_router.get("/check-conversation/{user_id}")
async def check_conversation_exists(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """检查与指定用户是否已有对话"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录"
        )
    
    user1_id = min(current_user.id, user_id)
    user2_id = max(current_user.id, user_id)
    
    thread_result = await db.execute(
        select(models.MessageThread).filter(
            models.MessageThread.user1_id == user1_id,
            models.MessageThread.user2_id == user2_id
        )
    )
    thread = thread_result.scalars().first()
    
    return {"has_conversation": thread is not None}

@private_message_router.get("/summary", response_model=schemas.MessageSummaryWithNotifications)
async def get_message_summary(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """获取当前用户的消息摘要（包含私信和通知的未读数量）"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录"
        )
    
    # 计算私信未读数量
    thread_result = await db.execute(
        select(models.MessageThread)
        .filter(
            or_(
                models.MessageThread.user1_id == current_user.id,
                models.MessageThread.user2_id == current_user.id
            )
        )
    )
    threads = thread_result.scalars().all()
    
    private_message_count = 0
    for thread in threads:
        if thread.user1_id == current_user.id:
            private_message_count += thread.user1_unread_count
        else:
            private_message_count += thread.user2_unread_count
    
    # 计算通知未读数量
    notification_result = await db.execute(
        select(func.count(models.Notification.id)).filter(
            models.Notification.user_id == current_user.id,
            models.Notification.is_read == 0
        )
    )
    notification_count = notification_result.scalar() or 0
    
    total_unread_count = private_message_count + notification_count
    
    return schemas.MessageSummaryWithNotifications(
        private_message_count=private_message_count,
        notification_count=notification_count,
        total_unread_count=total_unread_count
    )
