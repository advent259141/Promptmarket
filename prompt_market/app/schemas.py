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

class NotificationBase(BaseModel):
    """站内信基础模型"""
    title: str
    content: str
    notification_type: str
    related_id: Optional[int] = None

class NotificationCreate(NotificationBase):
    """创建站内信模型"""
    user_id: int

class Notification(NotificationBase):
    """站内信返回模型"""
    id: int
    user_id: int
    is_read: int
    created_at: datetime
    read_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        orm_mode = True

class NotificationUpdate(BaseModel):
    """更新站内信模型"""
    is_read: Optional[int] = None
    read_at: Optional[datetime] = None
