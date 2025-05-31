from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, func, desc # 导入 func 和 desc
from sqlalchemy.orm import joinedload, selectinload
from typing import List, Optional
from datetime import datetime, date, timedelta
import psutil
import os
import platform

from ..models import models
from ..schemas import schemas
from ..core.database import get_db
from .auth import get_current_admin  # 导入管理员鉴权依赖
from .notifications import create_system_notification  # 导入通知创建函数

# 创建管理员路由
admin_router = APIRouter()

@admin_router.put("/prompts/reject-all-pending", response_model=dict)
async def reject_all_pending_prompts(
    background_tasks: BackgroundTasks,
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
        
        # 创建拒绝通知
        await create_system_notification(
            db=db,
            user_id=user_id,
            title="提示审核未通过",
            content=f"很抱歉，您的提示「{title}」未通过审核。请检查内容是否符合平台规范，您可以修改后重新提交。",
            notification_type="prompt_rejected",
            related_prompt_id=prompt_id
        )
        
        count += 1
    
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
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)  # 添加管理员鉴权
):
    """审核通过一个prompt"""
    return await update_prompt_status(prompt_id, 1, db, background_tasks)

@admin_router.put("/prompts/{prompt_id}/reject", response_model=schemas.PromptList)
async def reject_prompt(
    prompt_id: int, 
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)  # 添加管理员鉴权
):
    """拒绝一个prompt"""
    return await update_prompt_status(prompt_id, 2, db, background_tasks)

@admin_router.put("/prompts/{prompt_id}/revert", response_model=schemas.PromptList)
async def revert_to_pending(
    prompt_id: int, 
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)  # 添加管理员鉴权
):
    """将已审核的prompt重置为待审核状态"""
    return await update_prompt_status(prompt_id, 0, db, background_tasks)

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

async def update_prompt_status(prompt_id: int, status: int, db: AsyncSession, background_tasks: BackgroundTasks):
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
    
    # 根据状态变化创建系统通知
    if old_status != status:
        notification_title = ""
        notification_content = ""
        notification_type = ""
        
        if status == 1:  # 审核通过
            notification_title = "提示审核通过"
            notification_content = f"您的提示「{title}」已通过审核，现在可以被其他用户查看了。"
            notification_type = "prompt_approved"
        elif status == 2:  # 审核拒绝
            notification_title = "提示审核未通过"
            notification_content = f"很抱歉，您的提示「{title}」未通过审核。请检查内容是否符合平台规范，您可以修改后重新提交。"
            notification_type = "prompt_rejected"
        elif status == 0 and old_status != 0:  # 重置为待审核
            notification_title = "提示状态已重置"
            notification_content = f"您的提示「{title}」的状态已重置为待审核，我们将重新进行审核。"
            notification_type = "prompt_reverted"
        
        # 创建通知
        if notification_title:
            await create_system_notification(
                db=db,
                user_id=user_id,
                title=notification_title,
                content=notification_content,
                notification_type=notification_type,
                related_prompt_id=prompt_id
            )
    
    await db.commit()
    
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

@admin_router.post("/send-notification", response_model=dict)
async def admin_send_notification(
    notification_request: schemas.SendNotificationRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """管理员发送通知给指定用户或所有用户"""
    target_user_ids = []
    
    if notification_request.broadcast:
        # 广播通知：获取所有用户ID
        user_query = select(models.User.id)
        result = await db.execute(user_query)
        target_user_ids = [row[0] for row in result.fetchall()]
        
        if not target_user_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="系统中没有注册用户"
            )
    else:
        # 单用户或批量发送
        if notification_request.user_id:
            target_user_ids = [notification_request.user_id]
        elif notification_request.user_ids:
            target_user_ids = notification_request.user_ids
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="必须提供user_id、user_ids或设置broadcast为true"
            )
        
        # 验证目标用户是否存在
        user_check_result = await db.execute(
            select(models.User.id).filter(
                models.User.id.in_(target_user_ids)
            )
        )
        existing_user_ids = [row[0] for row in user_check_result.fetchall()]
        
        if len(existing_user_ids) != len(target_user_ids):
            missing_ids = set(target_user_ids) - set(existing_user_ids)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"用户ID不存在: {list(missing_ids)}"
            )
    
    # 创建通知
    notifications = []
    for user_id in target_user_ids:
        notification = models.Notification(
            user_id=user_id,
            title=notification_request.title,
            content=notification_request.content,
            notification_type="admin",
            sender_id=current_admin.id,
            is_read=0
        )
        notifications.append(notification)
    
    db.add_all(notifications)
    await db.commit()
    
    message = "广播通知发送成功" if notification_request.broadcast else f"成功发送通知给 {len(target_user_ids)} 个用户"
    
    return {
        "message": message,
        "sent_count": len(target_user_ids),
        "status": "success"
    }

@admin_router.get("/users/search", response_model=List[schemas.User])
async def search_users(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """搜索用户（用于通知发送）"""
    # 按用户名或邮箱搜索
    query = select(models.User).filter(
        (models.User.username.ilike(f"%{q}%")) |
        (models.User.email.ilike(f"%{q}%"))
    ).limit(limit)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return users

@admin_router.get("/stats/server", response_model=dict)
async def get_server_stats(
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """获取服务器状态统计"""
    try:
        # 系统信息
        system_info = {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
        }
        
        # CPU信息
        cpu_info = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "cpu_count": psutil.cpu_count(),
            "cpu_count_logical": psutil.cpu_count(logical=True),
            "cpu_freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
        }
        
        # 内存信息
        memory = psutil.virtual_memory()
        memory_info = {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used,
            "free": memory.free,
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "used_gb": round(memory.used / (1024**3), 2),
        }
        
        # 磁盘信息
        disk = psutil.disk_usage('/')
        disk_info = {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": round((disk.used / disk.total) * 100, 2),
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
        }
        
        # 网络IO
        net_io = psutil.net_io_counters()
        network_info = {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "bytes_sent_mb": round(net_io.bytes_sent / (1024**2), 2),
            "bytes_recv_mb": round(net_io.bytes_recv / (1024**2), 2),
        }
        
        # 进程信息
        current_process = psutil.Process()
        process_info = {
            "pid": current_process.pid,
            "memory_percent": current_process.memory_percent(),
            "cpu_percent": current_process.cpu_percent(),
            "memory_info": current_process.memory_info()._asdict(),
            "create_time": current_process.create_time(),
            "num_threads": current_process.num_threads(),
        }
        
        # 数据库统计
        # 用户总数
        users_count_query = select(func.count(models.User.id))
        users_count_result = await db.execute(users_count_query)
        total_users = users_count_result.scalar()
        
        # Prompt总数
        prompts_count_query = select(func.count(models.Prompt.id))
        prompts_count_result = await db.execute(prompts_count_query)
        total_prompts = prompts_count_result.scalar()
        
        # 各状态的Prompt数量
        pending_prompts_query = select(func.count(models.Prompt.id)).filter(models.Prompt.status == 0)
        pending_prompts_result = await db.execute(pending_prompts_query)
        pending_prompts = pending_prompts_result.scalar()
        
        approved_prompts_query = select(func.count(models.Prompt.id)).filter(models.Prompt.status == 1)
        approved_prompts_result = await db.execute(approved_prompts_query)
        approved_prompts = approved_prompts_result.scalar()
        
        rejected_prompts_query = select(func.count(models.Prompt.id)).filter(models.Prompt.status == 2)
        rejected_prompts_result = await db.execute(rejected_prompts_query)
        rejected_prompts = rejected_prompts_result.scalar()
        
        # 评论总数
        comments_count_query = select(func.count(models.Comment.id))
        comments_count_result = await db.execute(comments_count_query)
        total_comments = comments_count_result.scalar()
        
        # 今日注册用户数
        today = date.today()
        today_users_query = select(func.count(models.User.id)).filter(
            func.date(models.User.created_at) == today
        )
        today_users_result = await db.execute(today_users_query)
        today_new_users = today_users_result.scalar()
        
        # 今日提交的Prompt数
        today_prompts_query = select(func.count(models.Prompt.id)).filter(
            func.date(models.Prompt.created_at) == today
        )
        today_prompts_result = await db.execute(today_prompts_query)
        today_new_prompts = today_prompts_result.scalar()
        
        database_stats = {
            "total_users": total_users,
            "total_prompts": total_prompts,
            "pending_prompts": pending_prompts,
            "approved_prompts": approved_prompts,
            "rejected_prompts": rejected_prompts,
            "total_comments": total_comments,
            "today_new_users": today_new_users,
            "today_new_prompts": today_new_prompts,
        }
        
        return {
            "system": system_info,
            "cpu": cpu_info,
            "memory": memory_info,
            "disk": disk_info,
            "network": network_info,
            "process": process_info,
            "database": database_stats,
            "timestamp": datetime.now().isoformat(),
        }
        
    except Exception as e:
        # 如果psutil不可用或其他错误，返回基本信息
        return {
            "error": f"Unable to get server stats: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }

# 站公告管理相关API
@admin_router.post("/announcement", response_model=schemas.SiteAnnouncement)
async def create_site_announcement(
    announcement: schemas.SiteAnnouncementCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """发布站公告 - 会删除旧公告并创建新公告"""
    # 先删除现有的活跃公告
    await db.execute(
        delete(models.SiteAnnouncement).where(models.SiteAnnouncement.is_active == 1)
    )
    
    # 创建新公告
    new_announcement = models.SiteAnnouncement(
        title=announcement.title,
        content=announcement.content,
        created_by=current_admin.id,
        is_active=1
    )
    
    db.add(new_announcement)
    await db.commit()
    await db.refresh(new_announcement)
    
    # 加载创建者信息
    await db.refresh(new_announcement, ['creator'])
    
    return new_announcement

@admin_router.delete("/announcement", response_model=dict)
async def delete_site_announcement(
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """删除当前站公告"""
    # 删除所有活跃公告
    result = await db.execute(
        delete(models.SiteAnnouncement).where(models.SiteAnnouncement.is_active == 1)
    )
    
    await db.commit()
    
    deleted_count = result.rowcount
    if deleted_count > 0:
        return {"message": f"成功删除 {deleted_count} 条站公告", "status": "success"}
    else:
        return {"message": "没有找到需要删除的站公告", "status": "info"}

@admin_router.get("/announcement", response_model=Optional[schemas.SiteAnnouncement])
async def get_current_announcement(
    db: AsyncSession = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """获取当前活跃的站公告"""
    query = select(models.SiteAnnouncement).options(
        joinedload(models.SiteAnnouncement.creator)
    ).filter(models.SiteAnnouncement.is_active == 1).order_by(
        models.SiteAnnouncement.created_at.desc()
    )
    
    result = await db.execute(query)
    announcement = result.scalars().first()
    
    return announcement
