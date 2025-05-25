from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import or_, func
from sqlalchemy.dialects.sqlite import insert
from typing import List, Optional
import datetime

from . import models, schemas
from .database import get_db, create_tables
from . import auth

router = APIRouter()

@router.on_event("startup")
async def on_startup():
    await create_tables()
    
    # 创建默认用户（如果不存在）
    db_generator = get_db()
    try:
        from .auth import get_password_hash
        db = await db_generator.__anext__()
        
        result = await db.execute(select(models.User).filter(models.User.id == 1))
        default_user = result.scalars().first()
        if not default_user:
            # 为默认用户生成哈希密码
            hashed_password = get_password_hash("default_password")
            default_user = models.User(id=1, username="default_user", hashed_password=hashed_password)
            db.add(default_user)
            await db.commit()
    finally:
        # 使用生成器正确关闭数据库连接
        try:
            await db_generator.aclose()
        except:
            pass

@router.post("/prompts/", response_model=schemas.Prompt, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    prompt: schemas.PromptCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """创建Prompt - 需要用户登录"""
    # 检查用户是否已登录
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录才能上传Prompt"
        )
    
    # 提取标签和验证码令牌，避免它们被直接传递给Prompt模型
    prompt_data = prompt.model_dump()
    tags_data = prompt_data.pop("tags", [])
    
    # 创建Prompt，使用当前用户的ID，默认状态为0（待审核）
    db_prompt = models.Prompt(**prompt_data, user_id=current_user.id, status=0)
    db.add(db_prompt)
    
    # 处理标签（最多5个）
    for tag_name in tags_data[:5]:  # 限制最多5个标签
        if tag_name:  # 确保标签名不为空
            # 查找或创建标签
            result = await db.execute(select(models.Tag).filter(models.Tag.name == tag_name))
            tag = result.scalars().first()
            if not tag:
                tag = models.Tag(name=tag_name)
                db.add(tag)
            
            # 将标签添加到prompt
            db_prompt.tags.append(tag)
    
    await db.commit()
    await db.refresh(db_prompt)
    
    # 重新查询以确保标签关系已完全加载，同时预加载owner和comments关系
    query = select(models.Prompt).options(
        joinedload(models.Prompt.tags),
        joinedload(models.Prompt.owner),
        joinedload(models.Prompt.comments).joinedload(models.Comment.user)
    ).filter(models.Prompt.id == db_prompt.id)
    result = await db.execute(query)
    db_prompt = result.scalars().first()
    return db_prompt

@router.get("/prompts/", response_model=List[schemas.PromptList])
async def read_prompts(skip: int = 0, limit: int = 10, search: Optional[str] = None, tag: Optional[str] = None, 
                     sort_by: Optional[str] = None, is_r18: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    # 使用joinedload预加载标签和用户信息，避免n+1查询问题
    # 只返回审核状态为1(已通过)的prompt
    # 注意：这里不加载评论关系，避免在列表页面触发大量评论加载
    query = select(models.Prompt).options(
        joinedload(models.Prompt.tags),
        joinedload(models.Prompt.owner)
    ).filter(models.Prompt.status == 1)
    
    # 根据R18参数筛选
    if is_r18 is not None:
        query = query.filter(models.Prompt.is_r18 == is_r18)
      # 如果提供了搜索关键词，使用标题、描述以及标签进行模糊查询
    if search:
        search = f"%{search}%"  # 添加模糊匹配的百分号
        # 首先获取包含与搜索关键词匹配的标签的prompt_id
        tag_query = select(models.Prompt.id).join(models.Prompt.tags).filter(models.Tag.name.ilike(search))
        tag_result = await db.execute(tag_query)
        tag_prompt_ids = [id for id, in tag_result.fetchall()]
        
        # 然后创建复合查询：标题或描述中包含关键词，或者prompt_id在tag_prompt_ids中
        query = query.filter(or_(
            models.Prompt.title.ilike(search),
            models.Prompt.description.ilike(search),
            models.Prompt.id.in_(tag_prompt_ids)
        ))
    
    # 如果提供了标签名称，根据标签过滤
    if tag:
        query = query.join(models.Prompt.tags).filter(models.Tag.name == tag)
    
    # 根据 sort_by 参数添加排序逻辑
    if sort_by == "upload_time_desc":
        query = query.order_by(models.Prompt.created_at.desc())
    elif sort_by == "upload_time_asc":
        query = query.order_by(models.Prompt.created_at.asc())
    elif sort_by == "views_desc":
        query = query.order_by(models.Prompt.views.desc())
    elif sort_by == "likes_desc":
        query = query.order_by(models.Prompt.likes.desc())
    else: # 默认为上传时间（新到老）
        query = query.order_by(models.Prompt.created_at.desc())

    # 应用分页
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    prompts = result.scalars().unique().all()
    return prompts

@router.get("/prompts/{prompt_id}", response_model=schemas.Prompt)
async def read_prompt(prompt_id: int, db: AsyncSession = Depends(get_db)):
    # 预加载标签、评论、评论的用户以及prompt的所有者
    query = select(models.Prompt).options(
        joinedload(models.Prompt.tags),
        joinedload(models.Prompt.owner),
        joinedload(models.Prompt.comments).joinedload(models.Comment.user)
    ).filter(models.Prompt.id == prompt_id, models.Prompt.status == 1)
    result = await db.execute(query)
    db_prompt = result.scalars().first()
    if db_prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    # 检查审核状态，只有已通过的prompt才能被访问
    if db_prompt.status != 1:
        raise HTTPException(status_code=404, detail="Prompt not found or not approved")
    
    # 增加浏览量
    db_prompt.views += 1
    
    # 同时更新daily_views表中的今日浏览量
    import datetime
    today = datetime.date.today()
    
    # 查询今天的记录是否存在
    daily_views_query = select(models.DailyViews).filter(models.DailyViews.date == today)
    daily_views_result = await db.execute(daily_views_query)
    daily_views = daily_views_result.scalar_one_or_none()
    
    if daily_views:
        # 如果今天的记录已存在，增加浏览量
        daily_views.views += 1
    else:
        # 如果今天的记录不存在，创建新记录
        new_daily_views = models.DailyViews(date=today, views=1)
        db.add(new_daily_views)
    
    await db.commit()
    await db.refresh(db_prompt)
    
    return db_prompt

@router.get("/prompts/{prompt_id}/edit", response_model=schemas.PromptForEdit)
async def get_prompt_for_edit(
    prompt_id: int, 
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """获取用户自己的Prompt用于编辑 - 不限制状态，不加载评论以提高性能"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录才能获取Prompt详情"
        )
    
    # 预加载标签信息，但不加载评论以提高性能
    query = select(models.Prompt).options(
        joinedload(models.Prompt.tags)
    ).filter(models.Prompt.id == prompt_id)
    result = await db.execute(query)
    db_prompt = result.scalars().first()
    
    if db_prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    # 检查权限：只有prompt作者可以获取编辑信息
    if db_prompt.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能编辑自己的Prompt"
        )
    
    return db_prompt

@router.put("/prompts/{prompt_id}/like")
async def like_prompt(prompt_id: int, db: AsyncSession = Depends(get_db)):
    # 使用joinedload预加载标签
    query = select(models.Prompt).options(joinedload(models.Prompt.tags)).filter(models.Prompt.id == prompt_id)
    result = await db.execute(query)
    db_prompt = result.scalars().first()
    if db_prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    db_prompt.likes += 1
    await db.commit()
    await db.refresh(db_prompt)
    
    # 只返回状态和ID
    return {"status": "success", "id": prompt_id, "likes": db_prompt.likes}

@router.put("/prompts/{prompt_id}/dislike")
async def dislike_prompt(prompt_id: int, db: AsyncSession = Depends(get_db)):
    # 使用joinedload预加载标签
    query = select(models.Prompt).options(joinedload(models.Prompt.tags)).filter(models.Prompt.id == prompt_id)
    result = await db.execute(query)
    db_prompt = result.scalars().first()
    if db_prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    db_prompt.dislikes += 1
    await db.commit()
    await db.refresh(db_prompt)
    
    # 只返回状态和ID
    return {"status": "success", "id": prompt_id, "dislikes": db_prompt.dislikes}

@router.get("/tags/", response_model=List[schemas.Tag])
async def read_tags(db: AsyncSession = Depends(get_db)):
    """获取所有标签列表"""
    query = select(models.Tag)
    result = await db.execute(query)
    tags = result.scalars().all()
    return tags

# 评论相关的API端点
@router.post("/prompts/{prompt_id}/comments/", response_model=schemas.Comment)
async def create_comment(
    prompt_id: int, 
    comment: schemas.CommentCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """创建评论 - 需要用户登录"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录才能发表评论"
        )
    
    # 首先检查prompt是否存在且已通过审核
    prompt_query = select(models.Prompt).filter(models.Prompt.id == prompt_id, models.Prompt.status == 1)
    result = await db.execute(prompt_query)
    db_prompt = result.scalars().first()
    if db_prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found or not approved")
    
    # 创建评论，使用当前登录用户的ID
    comment_data = comment.model_dump()
    # 移除user_id字段（如果存在），使用当前用户的ID
    comment_data.pop('user_id', None)
    db_comment = models.Comment(**comment_data, prompt_id=prompt_id, user_id=current_user.id)
    db.add(db_comment)
    await db.commit()
    await db.refresh(db_comment)
    
    # 发送评论通知给Prompt作者
    try:
        from .notification_service import NotificationService
        await NotificationService.create_comment_notification(
            db=db,
            prompt_author_id=db_prompt.user_id,
            commenter_id=current_user.id,
            commenter_username=current_user.username,
            prompt_id=prompt_id,
            prompt_title=db_prompt.title,
            comment_content=comment.content
        )
    except Exception as e:
        # 通知发送失败不应该影响评论创建，只记录错误
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"发送评论通知失败: {e}")
    
    return db_comment

@router.get("/prompts/{prompt_id}/comments/", response_model=List[schemas.CommentWithUser])
async def read_comments(
    prompt_id: int, 
    skip: int = 0, 
    limit: int = 50, 
    db: AsyncSession = Depends(get_db)
):
    """获取指定prompt的评论列表 - 不需要登录，包含用户信息"""
    # 首先检查prompt是否存在且已通过审核
    prompt_query = select(models.Prompt).filter(models.Prompt.id == prompt_id, models.Prompt.status == 1)
    result = await db.execute(prompt_query)
    db_prompt = result.scalars().first()
    if db_prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found or not approved")
    
    # 获取评论列表并预加载用户信息
    from sqlalchemy.orm import joinedload
    query = (
        select(models.Comment)
        .options(joinedload(models.Comment.user))
        .filter(models.Comment.prompt_id == prompt_id)
        .order_by(models.Comment.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    comments = result.scalars().unique().all()
    return comments

@router.delete("/comments/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: int, 
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """删除评论 - 只有评论作者或管理员可以删除"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录才能删除评论"
        )
    
    # 查找评论
    query = select(models.Comment).filter(models.Comment.id == comment_id)
    result = await db.execute(query)
    db_comment = result.scalars().first()
    if db_comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # 检查权限：只有评论作者或管理员可以删除
    if db_comment.user_id != current_user.id and current_user.is_admin != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能删除自己的评论"
        )
    
    # 删除评论
    await db.delete(db_comment)
    await db.commit()
    return {"status": "success"}


@router.put("/prompts/{prompt_id}", response_model=schemas.PromptList)
async def update_prompt(
    prompt_id: int,
    prompt_update: schemas.PromptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """用户更新自己的Prompt"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录才能编辑Prompt"
        )
    
    # 查找prompt
    query = select(models.Prompt).options(
        joinedload(models.Prompt.tags),
        joinedload(models.Prompt.owner)
    ).filter(models.Prompt.id == prompt_id)
    result = await db.execute(query)
    prompt = result.scalars().first()
    
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    # 检查权限：只有prompt作者可以编辑
    if prompt.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能编辑自己的Prompt"
        )
    
    # 提取标签数据
    prompt_data = prompt_update.model_dump()
    tags_data = prompt_data.pop("tags", [])
    
    # 更新prompt基本信息
    for field, value in prompt_data.items():
        setattr(prompt, field, value)
    
    # 将prompt状态重置为待审核（用户编辑后需要重新审核）
    prompt.status = 0
    prompt.updated_at = datetime.datetime.now()
    
    # 清除现有标签
    prompt.tags.clear()
    
    # 添加新标签（最多5个）
    for tag_name in tags_data[:5]:
        if tag_name:
            # 查找或创建标签
            tag_result = await db.execute(select(models.Tag).filter(models.Tag.name == tag_name))
            tag = tag_result.scalars().first()
            if not tag:
                tag = models.Tag(name=tag_name)
                db.add(tag)
            
            # 将标签添加到prompt
            prompt.tags.append(tag)
    
    await db.commit()
    await db.refresh(prompt)
    
    return prompt


@router.delete("/prompts/{prompt_id}", status_code=204)
async def delete_prompt(
    prompt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """用户删除自己的Prompt"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录才能删除Prompt"
        )
    
    # 查找prompt
    query = select(models.Prompt).filter(models.Prompt.id == prompt_id)
    result = await db.execute(query)
    prompt = result.scalars().first()
    
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    # 检查权限：只有prompt作者可以删除
    if prompt.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能删除自己的Prompt"
        )
    
    # 删除prompt
    await db.delete(prompt)
    await db.commit()
    
    return {"status": "success"}
