from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, func, desc # 导入 func 和 desc
from sqlalchemy.orm import joinedload, selectinload
from typing import List, Optional
from datetime import datetime, date, timedelta

from . import models, schemas
from .database import get_db
from .auth import get_current_admin  # 导入管理员鉴权依赖
from .notification_service import NotificationService  # 导入通知服务

# 创建管理员路由
admin_router = APIRouter()

@admin_router.put("/prompts/reject-all-pending", response_model=dict)
async def reject_all_pending_prompts(
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """一键拒绝所有待审核的Prompt"""
    query = select(models.Prompt).filter(models.Prompt.status == 0)
    result = await db.execute(query)
    pending_prompts = result.scalars().all()

    if not pending_prompts:
        return {"message": "没有待审核的Prompt", "count": 0}

    count = 0
    for prompt in pending_prompts:
        # 保存必要信息用于发送通知
        user_id = prompt.user_id
        prompt_id = prompt.id
        title = prompt.title
        
        # 更新状态
        prompt.status = 2  # 2 表示已拒绝
        prompt.updated_at = datetime.now()
        count += 1
        
        # 为每个被拒绝的Prompt发送通知
        try:
            await NotificationService.create_prompt_review_notification(
                db=db,
                user_id=user_id,
                prompt_id=prompt_id,
                prompt_title=title,
                is_approved=False
            )
        except Exception as e:
            # 通知发送失败不应该影响主要流程，只记录日志
            print(f"发送审核通知失败(Prompt ID: {prompt_id}): {e}")
    
    await db.commit()
    return {"message": f"成功拒绝 {count} 个待审核的Prompt", "count": count}

@admin_router.delete("/prompts/delete-all-rejected", response_model=dict)
async def delete_all_rejected_prompts(
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """一键删除所有已拒绝的Prompt"""
    # 首先查询所有已拒绝的Prompt
    query = select(models.Prompt).filter(models.Prompt.status == 2).options(joinedload(models.Prompt.tags))
    result = await db.execute(query)
    rejected_prompts = result.scalars().unique().all()
    
    if not rejected_prompts:
        return {"message": "没有已拒绝的Prompt可删除", "count": 0}
    
    # 分别删除每个Prompt及其关联的标签关系
    deleted_count = 0
    for prompt in rejected_prompts:
        # 先清除标签关系（这会删除prompt_tag表中的关联记录）
        prompt.tags.clear()
        # 然后删除prompt
        await db.delete(prompt)
        deleted_count += 1
    
    await db.commit()
    
    return {"message": f"成功删除 {deleted_count} 个已拒绝的Prompt", "count": deleted_count}

@admin_router.get("/prompts/", response_model=List[schemas.PromptList])
async def admin_get_prompts(
    status: Optional[int] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)  # 添加管理员鉴权
):
    """
    获取所有提示，可以按状态筛选
    status: 0-待审核, 1-已通过, 2-已拒绝, None-所有
    """
    # 准备查询，使用joinedload预加载标签和owner关系
    query = select(models.Prompt).options(
        joinedload(models.Prompt.tags),
        joinedload(models.Prompt.owner)
    )
    
    # 如果提供了状态过滤条件
    if status is not None:
        query = query.filter(models.Prompt.status == status)
    
    # 按创建时间降序排序，最新的排在最上面
    query = query.order_by(models.Prompt.created_at.desc())
    
    # 应用分页
    query = query.offset(skip).limit(limit)
    
    # 执行查询
    result = await db.execute(query)
    prompts = result.scalars().unique().all()
    
    return prompts

@admin_router.get("/prompts/{prompt_id}", response_model=schemas.Prompt)
async def admin_get_prompt(
    prompt_id: int, 
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)  # 添加管理员鉴权
):
    """获取单个prompt的详细信息"""
    # 使用joinedload预加载关系，避免N+1查询
    query = select(models.Prompt).options(
        joinedload(models.Prompt.tags),
        joinedload(models.Prompt.owner),
        joinedload(models.Prompt.comments).joinedload(models.Comment.user)
    ).filter(models.Prompt.id == prompt_id)
    result = await db.execute(query)
    prompt = result.scalars().unique().first()
    
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    # 管理员查看不增加浏览量
    
    return prompt

@admin_router.put("/prompts/{prompt_id}/approve", response_model=schemas.PromptList)
async def approve_prompt(
    prompt_id: int, 
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)  # 添加管理员鉴权
):
    """审核通过一个prompt"""
    return await update_prompt_status(prompt_id, 1, db)

@admin_router.put("/prompts/{prompt_id}/reject", response_model=schemas.PromptList)
async def reject_prompt(
    prompt_id: int, 
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)  # 添加管理员鉴权
):
    """拒绝一个prompt"""
    return await update_prompt_status(prompt_id, 2, db)

@admin_router.put("/prompts/{prompt_id}/revert", response_model=schemas.PromptList)
async def revert_to_pending(
    prompt_id: int, 
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)  # 添加管理员鉴权
):
    """将已审核的prompt重置为待审核状态"""
    return await update_prompt_status(prompt_id, 0, db)

@admin_router.put("/prompts/{prompt_id}/update", response_model=schemas.PromptList)
async def update_prompt_content(
    prompt_id: int,
    prompt_update: schemas.PromptCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)  # 添加管理员鉴权
):
    """更新prompt的标题、内容、描述和R18状态"""
    # 查找prompt
    query = select(models.Prompt).options(
        joinedload(models.Prompt.tags),
        joinedload(models.Prompt.owner)
    ).filter(models.Prompt.id == prompt_id)
    result = await db.execute(query)
    prompt = result.scalars().unique().first()
    
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    # 更新prompt内容
    prompt.title = prompt_update.title
    prompt.content = prompt_update.content
    prompt.description = prompt_update.description
    # 添加对is_r18字段的支持
    prompt.is_r18 = prompt_update.is_r18
    prompt.updated_at = datetime.now()

    # 处理标签更新
    if prompt_update.tags is not None:
        # 清空现有标签
        prompt.tags.clear()
        await db.flush() # 确保清除操作被执行

        # 添加新标签
        for tag_name in prompt_update.tags:
            if tag_name: # 确保标签名不为空
                # 查找或创建标签
                tag_result = await db.execute(select(models.Tag).filter(models.Tag.name == tag_name))
                tag = tag_result.scalars().first()
                if not tag:
                    tag = models.Tag(name=tag_name)
                    db.add(tag)
                    await db.flush() # 确保新标签在添加到prompt前有ID
                prompt.tags.append(tag)
    
    await db.commit()
    await db.refresh(prompt)
    
    return prompt

@admin_router.delete("/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: int, 
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)  # 添加管理员鉴权
):
    """删除一个prompt"""
    # 查找prompt
    query = select(models.Prompt).filter(models.Prompt.id == prompt_id)
    result = await db.execute(query)
    prompt = result.scalars().first()
    
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    # 删除prompt
    await db.delete(prompt)
    await db.commit()
    
    return {"message": f"Prompt {prompt_id} has been deleted", "status": "success"}

async def update_prompt_status(prompt_id: int, status: int, db: AsyncSession):
    """更新prompt的审核状态"""
    # 先获取prompt基本信息，避免复杂的关系加载
    query = select(models.Prompt).filter(models.Prompt.id == prompt_id)
    result = await db.execute(query)
    prompt = result.scalars().first()
    
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    # 记录之前的状态和必要信息，用于发送通知
    old_status = prompt.status
    user_id = prompt.user_id
    title = prompt.title
    
    # 更新状态
    prompt.status = status
    await db.commit()
    
    # 根据状态变化发送相应通知
    if old_status == 0 and status in [1, 2]:
        # 状态从待审核(0)变为通过(1)或拒绝(2)，发送审核结果通知
        try:
            await NotificationService.create_prompt_review_notification(
                db=db,
                user_id=user_id,
                prompt_id=prompt_id,
                prompt_title=title,
                is_approved=(status == 1)
            )
        except Exception as e:
            # 通知发送失败不应该影响主要流程，只记录日志
            print(f"发送审核通知失败: {e}")
    elif old_status in [1, 2] and status == 0:
        # 状态从已审核(1或2)变为待审核(0)，发送撤回通知
        try:
            await NotificationService.create_prompt_revert_notification(
                db=db,
                user_id=user_id,
                prompt_id=prompt_id,
                prompt_title=title
            )
        except Exception as e:
            # 通知发送失败不应该影响主要流程，只记录日志
            print(f"发送撤回通知失败: {e}")
    
    # 重新获取带关系的数据用于返回，使用joinedload而不是selectinload
    query_with_relations = select(models.Prompt).options(
        joinedload(models.Prompt.tags),
        joinedload(models.Prompt.owner)
    ).filter(models.Prompt.id == prompt_id)
    result = await db.execute(query_with_relations)
    updated_prompt = result.scalars().unique().first()
    
    return updated_prompt

@admin_router.get("/users/", response_model=List[schemas.User])
async def admin_get_users(
    skip: int = 0, 
    limit: int = 100, 
    oauth_provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)  # 添加管理员鉴权
):
    """
    获取所有用户，可以按OAuth提供商筛选
    oauth_provider: 'github', 'google', 'facebook', None-所有
    """
    # 准备查询
    query = select(models.User)
    
    # 如果提供了OAuth提供商过滤条件
    if oauth_provider:
        query = query.filter(models.User.oauth_provider == oauth_provider)
    
    # 按创建时间降序排序，最新的排在最上面
    query = query.order_by(models.User.created_at.desc())
    
    # 应用分页
    query = query.offset(skip).limit(limit)
    
    # 执行查询
    result = await db.execute(query)
    users = result.scalars().all()
    
    return users

@admin_router.get("/stats/views", response_model=dict)
async def get_views_stats(
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """获取网站浏览量统计（日浏览量和累计浏览量）"""
    # 获取当前日期
    today = date.today()
    
    # 获取今日浏览量
    today_stats_query = select(models.DailyViews).filter(models.DailyViews.date == today)
    today_stats_result = await db.execute(today_stats_query)
    today_stats = today_stats_result.scalar_one_or_none()
    
    daily_views = today_stats.views if today_stats else 0
    
    # 获取累计浏览量
    total_views_query = select(func.sum(models.Prompt.views))
    total_views_result = await db.execute(total_views_query)
    total_views = total_views_result.scalar() or 0
    
    # 获取过去7天的浏览量趋势
    week_ago = today - timedelta(days=7)
    weekly_trend_query = select(models.DailyViews).filter(models.DailyViews.date >= week_ago).order_by(models.DailyViews.date)
    weekly_trend_result = await db.execute(weekly_trend_query)
    weekly_trend = weekly_trend_result.scalars().all()
    
    # 转换为字典格式，方便前端处理
    trend_data = []
    current = week_ago
    
    # 填充过去7天的数据，如果某天没有记录则显示为0
    while current <= today:
        day_data = next(({"date": day.date.isoformat(), "views": day.views} for day in weekly_trend if day.date == current), 
                        {"date": current.isoformat(), "views": 0})
        trend_data.append(day_data)
        current += timedelta(days=1)
    
    return {
        "daily_views": daily_views,
        "total_views": total_views,
        "weekly_trend": trend_data
    }

@admin_router.delete("/comments/{comment_id}", status_code=204)
async def admin_delete_comment(
    comment_id: int, 
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """管理员删除评论 - 管理员可以删除任何评论"""
    # 查找评论
    query = select(models.Comment).filter(models.Comment.id == comment_id)
    result = await db.execute(query)
    db_comment = result.scalars().first()
    if db_comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # 删除评论
    await db.delete(db_comment)
    await db.commit()
    return {"status": "success"}
