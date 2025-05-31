# -*- coding: utf-8 -*-
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Table, UniqueConstraint, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func # 导入 func
from ..core.database import Base
import sqlalchemy
import datetime

# 定义Prompt和Tag的多对多关系表
prompt_tag = Table(
    "prompt_tag",
    Base.metadata,
    Column("prompt_id", Integer, ForeignKey("prompts.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True)
)

# 定义用户关注关系表
user_follow = Table(
    "user_follow",
    Base.metadata,
    Column("follower_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("following_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    sqlalchemy.UniqueConstraint('follower_id', 'following_id', name='_user_follow_uc'),
    sqlalchemy.CheckConstraint('follower_id != following_id', name='check_no_self_follow')
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False) # 明确长度并设为不可空
    hashed_password = Column(String(255), nullable=True) # 密码哈希，明确长度，OAuth用户可以为空
    email = Column(String(100), unique=True, index=True, nullable=True) # 邮箱，明确长度
    is_admin = Column(Integer, default=0) # 是否为管理员: 0-普通用户, 1-管理员
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # OAuth相关字段
    oauth_provider = Column(String(20), nullable=True) # 认证提供商: github, google, etc.
    oauth_id = Column(String(100), nullable=True, index=True) # 提供商中的用户ID
    avatar_url = Column(String(255), nullable=True) # 用户头像URL
    
    # 用于OAuth认证的索引：确保(oauth_provider, oauth_id)组合的唯一性
    __table_args__ = (
        sqlalchemy.UniqueConstraint('oauth_provider', 'oauth_id', name='_oauth_provider_id_uc'),
    )

    prompts = relationship("Prompt", back_populates="owner")
    
    # 关注关系
    # 我关注的人
    following = relationship(
        "User",
        secondary=user_follow,
        primaryjoin=id == user_follow.c.follower_id,
        secondaryjoin=id == user_follow.c.following_id,
        backref="followers",
        overlaps="followers"
    )

class Tag(Base):
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)
    
    # 多对多关系，通过prompt_tag表关联
    prompts = relationship("Prompt", secondary=prompt_tag, back_populates="tags")

class Prompt(Base):
    __tablename__ = "prompts"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), index=True, nullable=False) # 明确长度并设为不可空
    content = Column(Text, nullable=False) # Text 类型用于较长文本，并设为不可空
    description = Column(String(255)) # 明确长度
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    likes = Column(Integer, default=0)
    dislikes = Column(Integer, default=0)
    views = Column(Integer, default=0) # 新增：浏览量计数
    status = Column(Integer, default=0, index=True) # 审核状态: 0-待审核, 1-已通过, 2-已拒绝
    is_r18 = Column(Integer, default=0, index=True) # R18标识: 0-非R18, 1-R18
    
    owner = relationship("User", back_populates="prompts")
    # 多对多关系，通过prompt_tag表关联
    tags = relationship("Tag", secondary=prompt_tag, back_populates="prompts")
    # 一对多关系，一个prompt可以有多个评论
    comments = relationship("Comment", back_populates="prompt", cascade="all, delete-orphan")

class Comment(Base):
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False) # 评论内容
    prompt_id = Column(Integer, ForeignKey("prompts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, default=1) # 添加用户ID字段，默认值1表示系统用户
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 与Prompt的关系
    prompt = relationship("Prompt", back_populates="comments")
    # 与User的关系，使用joined策略预加载用户信息
    user = relationship("User", lazy="joined")

class DailyViews(Base):
    __tablename__ = "daily_views"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, default=datetime.date.today, index=True)
    views = Column(Integer, default=0)
    
    # 添加唯一约束来确保每天只有一条记录
    __table_args__ = (
        sqlalchemy.UniqueConstraint('date', name='_date_uc'),
    )

class PrivateMessage(Base):
    """私信模型"""
    __tablename__ = "private_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_read = Column(Integer, default=0, index=True)  # 0-未读, 1-已读
    
    # 建立与User的关系，使用joined策略预加载用户信息
    sender = relationship("User", foreign_keys=[sender_id], lazy="joined")
    receiver = relationship("User", foreign_keys=[receiver_id], lazy="joined")
    
    # 添加索引以优化查询性能
    __table_args__ = (
        sqlalchemy.Index('idx_sender_receiver', 'sender_id', 'receiver_id'),
        sqlalchemy.Index('idx_receiver_created', 'receiver_id', 'created_at'),
    )

class MessageThread(Base):
    """消息会话模型，用于管理两个用户之间的对话"""
    __tablename__ = "message_threads"
    
    id = Column(Integer, primary_key=True, index=True)
    user1_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user2_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    last_message_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    user1_unread_count = Column(Integer, default=0)  # user1的未读消息数量
    user2_unread_count = Column(Integer, default=0)  # user2的未读消息数量
    
    # 建立与User的关系
    user1 = relationship("User", foreign_keys=[user1_id], lazy="joined")
    user2 = relationship("User", foreign_keys=[user2_id], lazy="joined")
    
    # 确保两个用户之间只有一个会话
    __table_args__ = (
        sqlalchemy.UniqueConstraint('user1_id', 'user2_id', name='_user_thread_uc'),
        sqlalchemy.CheckConstraint('user1_id < user2_id', name='check_user_order'),
    )

class Notification(Base):
    """通知模型"""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)  # 通知标题
    content = Column(Text, nullable=False)  # 通知内容
    notification_type = Column(String(50), nullable=False, index=True)  # 通知类型：system, admin, prompt_approved, prompt_rejected, prompt_withdrawn
    is_read = Column(Integer, default=0, index=True)  # 0-未读, 1-已读
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    read_at = Column(DateTime(timezone=True), nullable=True)  # 阅读时间
    related_prompt_id = Column(Integer, ForeignKey("prompts.id"), nullable=True)  # 关联的prompt ID（如果适用）
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # 发送者ID（管理员通知时使用）
    
    # 建立关系
    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    related_prompt = relationship("Prompt", foreign_keys=[related_prompt_id], lazy="joined")
    sender = relationship("User", foreign_keys=[sender_id], lazy="joined")
    
    # 添加索引以优化查询性能
    __table_args__ = (
        sqlalchemy.Index('idx_user_created', 'user_id', 'created_at'),
        sqlalchemy.Index('idx_user_read', 'user_id', 'is_read'),
        sqlalchemy.Index('idx_notification_type', 'notification_type'),
    )

# 新增站公告模型
class SiteAnnouncement(Base):
    """站公告模型"""
    __tablename__ = "site_announcements"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)  # 公告标题
    content = Column(Text, nullable=False)  # 公告内容
    is_active = Column(Integer, default=1, index=True)  # 是否激活: 0-已删除, 1-激活
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # 创建者（管理员）ID
    
    # 与User的关系
    creator = relationship("User", foreign_keys=[created_by])
