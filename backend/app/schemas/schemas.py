from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class TagBase(BaseModel):
    name: str
    
class TagCreate(TagBase):
    pass

class Tag(TagBase):
    id: int
    
    class Config:
        from_attributes = True  # 替代已弃用的orm_mode
        orm_mode = True  # 保留向后兼容性

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None

class User(UserBase):
    id: int
    is_admin: int = 0
    oauth_provider: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None  # 添加创建时间字段

    class Config:
        from_attributes = True  # 替代已弃用的orm_mode
        orm_mode = True  # 保留向后兼容性

class CommentBase(BaseModel):
    content: str

class CommentCreate(CommentBase):
    user_id: Optional[int] = 1  # 默认为1，表示系统用户

class Comment(CommentBase):
    id: int
    prompt_id: int
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True  # 替代已弃用的orm_mode
        orm_mode = True  # 保留向后兼容性

class CommentWithUser(CommentBase):
    """包含用户信息的评论模型"""
    id: int
    prompt_id: int
    user_id: int
    created_at: datetime
    user: User  # 包含完整的用户信息
    
    class Config:
        from_attributes = True
        orm_mode = True

class PromptBase(BaseModel):
    title: str
    content: str
    description: Optional[str] = None
    is_r18: Optional[int] = 0  # 默认为非R18内容

class PromptCreate(PromptBase):
    tags: Optional[List[str]] = []  # 创建Prompt时可以提供标签名称列表

class PromptList(PromptBase):
    """用于列表展示的Prompt模型，不包含评论信息"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    likes: int = 0
    dislikes: int = 0
    views: int = 0
    status: int = 0
    is_r18: int = 0
    tags: List[Tag] = []
    owner: Optional[User] = None  # 添加作者信息
    
    class Config:
        from_attributes = True
        orm_mode = True

class PromptForEdit(PromptBase):
    """用于编辑的Prompt模型，不包含评论信息以提高性能"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    likes: int = 0
    dislikes: int = 0
    views: int = 0
    status: int = 0
    is_r18: int = 0
    tags: List[Tag] = []
    
    class Config:
        from_attributes = True
        orm_mode = True

class Prompt(PromptBase):
    """用于详情展示的Prompt模型，包含评论信息"""
    id: int
    user_id: int # 假设有用户系统
    created_at: datetime
    updated_at: datetime
    likes: int = 0
    dislikes: int = 0
    views: int = 0  # 新增：浏览量
    status: int = 0  # 审核状态: 0-待审核, 1-已通过, 2-已拒绝
    is_r18: int = 0  # R18标识: 0-非R18, 1-R18
    tags: List[Tag] = []  # 返回Prompt时包含标签对象列表
    owner: Optional[User] = None  # 添加作者信息
    comments: List[CommentWithUser] = []  # 返回Prompt时包含包含用户信息的评论列表
    
    class Config:
        from_attributes = True  # 替代已弃用的orm_mode
        orm_mode = True  # 保留向后兼容性

# OAuth相关模型
class GitHubUser(BaseModel):
    """GitHub用户信息模型"""
    id: int
    login: str
    avatar_url: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None

class OAuthRequest(BaseModel):
    """OAuth请求参数"""
    code: str
    state: Optional[str] = None

# 用户主页相关模型
class Stats(BaseModel):
    """统计信息模型"""
    total_prompts: int
    approved_prompts: int
    pending_prompts: int
    total_users: int
    total_views: int
    today_views: int

class UserStats(BaseModel):
    """用户统计信息"""
    total_prompts: int = 0
    total_likes: int = 0
    total_views: int = 0
    
    class Config:
        from_attributes = True

class UserProfile(BaseModel):
    """用户主页完整信息"""
    user: User
    prompts: List[PromptList] = []
    stats: UserStats
    
    class Config:
        from_attributes = True

# 聊天相关模型
class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str
    prompt_id: Optional[int] = None
    session_id: Optional[str] = None
    model_type: Optional[str] = "gemini"  # 默认使用gemini模型

class ChatResponse(BaseModel):
    """聊天响应模型"""
    message: str
    session_id: str
    model_type: str

class ChatMessage(BaseModel):
    """聊天消息模型"""
    role: str  # system, user, assistant
    content: str
    timestamp: datetime
    
    class Config:
        from_attributes = True

# 用于消息服务的模型
class MessageSummary(BaseModel):
    """消息摘要模型"""
    unread_count: int
    total_count: int

class MessageResponse(BaseModel):
    """消息响应模型"""
    id: int
    title: str
    content: str
    message_type: str
    is_read: int
    created_at: datetime
    read_at: Optional[datetime] = None
    related_prompt_id: Optional[int] = None
    
    class Config:
        from_attributes = True

class MessagesResponse(BaseModel):
    """消息列表响应模型"""
    messages: List[MessageResponse]
    total: int
    page: int
    has_more: bool

class PaginatedPromptsResponse(BaseModel):
    """分页Prompt响应模型"""
    prompts: List[PromptList]
    total: int
    page: int
    per_page: int
    has_more: bool
    
    class Config:
        from_attributes = True

# 私信相关的Pydantic模型
class PrivateMessageBase(BaseModel):
    content: str

class PrivateMessageCreate(PrivateMessageBase):
    receiver_id: int

class PrivateMessage(PrivateMessageBase):
    id: int
    sender_id: int
    receiver_id: int
    created_at: datetime
    is_read: int
    
    class Config:
        from_attributes = True
        orm_mode = True

class PrivateMessageWithUser(PrivateMessageBase):
    """包含用户信息的私信模型"""
    id: int
    sender_id: int
    receiver_id: int
    created_at: datetime
    is_read: int
    sender: User
    receiver: User
    
    class Config:
        from_attributes = True
        orm_mode = True

class MessageThreadBase(BaseModel):
    pass

class MessageThread(MessageThreadBase):
    id: int
    user1_id: int
    user2_id: int
    last_message_at: datetime
    user1_unread_count: int
    user2_unread_count: int
    user1: User
    user2: User
    
    class Config:
        from_attributes = True
        orm_mode = True

class ConversationResponse(BaseModel):
    """对话响应模型"""
    thread_id: int
    other_user: User
    last_message_at: datetime
    unread_count: int
    latest_message: Optional[str] = None
    
    class Config:
        from_attributes = True

class SendMessageRequest(BaseModel):
    """发送消息请求模型"""
    receiver_id: int
    content: str

# 关注相关模型
class FollowRequest(BaseModel):
    """关注请求模型"""
    user_id: int

class FollowResponse(BaseModel):
    """关注响应模型"""
    message: str
    is_following: bool

class UserFollow(BaseModel):
    """用户关注信息"""
    user: User
    is_following: bool
    
    class Config:
        from_attributes = True

class FollowListResponse(BaseModel):
    """关注列表响应模型"""
    users: List[UserFollow]
    total: int

class UserProfileWithFollow(BaseModel):
    """包含关注信息的用户主页"""
    user: User
    prompts: List[PromptList] = []
    stats: UserStats
    is_following: bool
    followers_count: int
    following_count: int
    
    class Config:
        from_attributes = True

# 通知相关模型
class NotificationBase(BaseModel):
    title: str
    content: str
    notification_type: str

class NotificationCreate(NotificationBase):
    user_id: int
    related_prompt_id: Optional[int] = None
    sender_id: Optional[int] = None

class Notification(NotificationBase):
    id: int
    user_id: int
    is_read: int
    created_at: datetime
    read_at: Optional[datetime] = None
    related_prompt_id: Optional[int] = None
    sender_id: Optional[int] = None
    
    class Config:
        from_attributes = True

class NotificationWithDetails(Notification):
    """包含详细信息的通知模型"""
    sender: Optional[User] = None
    related_prompt: Optional[PromptList] = None
    
    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    """通知响应模型"""
    notifications: List[NotificationWithDetails]
    total: int
    unread_count: int

class SendNotificationRequest(BaseModel):
    """发送通知请求模型"""
    user_ids: Optional[List[int]] = None  # 接收通知的用户ID列表（批量发送）
    user_id: Optional[int] = None  # 单个用户ID（单用户发送）
    broadcast: Optional[bool] = False  # 是否为广播通知（发送给所有用户）
    title: str
    content: str
    notification_type: str = "admin"

class MessageSummaryWithNotifications(BaseModel):
    """包含通知的消息摘要模型"""
    private_message_count: int
    notification_count: int
    total_unread_count: int

# 站公告相关模型
class SiteAnnouncementBase(BaseModel):
    title: str
    content: str

class SiteAnnouncementCreate(SiteAnnouncementBase):
    pass

class SiteAnnouncement(SiteAnnouncementBase):
    id: int
    is_active: int
    created_at: datetime
    created_by: int
    creator: Optional[User] = None
    
    class Config:
        from_attributes = True
        orm_mode = True
