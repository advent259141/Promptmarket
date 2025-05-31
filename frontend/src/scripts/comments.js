// 评论相关功能
let commentsLoaded = false; // 标记评论是否已加载

// 加载指定prompt的评论
async function loadComments(promptId) {
    if (!promptId) return;
    
    try {
        // 显示加载中
        const commentsLoading = document.getElementById('comments-loading');
        const noCommentsMessage = document.getElementById('no-comments-message');
        const commentsList = document.getElementById('comments-list');
        
        commentsLoading.style.display = 'block';
        noCommentsMessage.style.display = 'none';
        
        // 清除之前的评论（保留加载和无评论提示元素）
        Array.from(commentsList.children).forEach(child => {
            if (child !== commentsLoading && child !== noCommentsMessage) {
                child.remove();
            }
        });
        
        // 获取评论数据
        const response = await fetch(`${API_BASE_URL}/prompts/${promptId}/comments/`);
        
        if (!response.ok) {
            throw new Error('获取评论失败');
        }
        
        const comments = await response.json();
        
        // 更新评论计数
        document.getElementById('comments-count').textContent = `(${comments.length})`;
        
        // 隐藏加载中
        commentsLoading.style.display = 'none';
        
        // 如果没有评论，显示无评论提示
        if (comments.length === 0) {
            noCommentsMessage.style.display = 'block';
            return;
        }
        
        // 渲染评论列表
        comments.forEach(comment => {
            const commentElement = createCommentElement(comment);
            commentsList.appendChild(commentElement);
        });
        
        commentsLoaded = true;
    } catch (error) {
        console.error('加载评论失败:', error);
        document.getElementById('comments-loading').style.display = 'none';
        document.getElementById('no-comments-message').textContent = '加载评论失败，请稍后重试';
        document.getElementById('no-comments-message').style.display = 'block';
    }
}

// 创建评论元素
function createCommentElement(comment) {
    const commentElement = document.createElement('div');
    commentElement.className = 'comment-item';
    commentElement.setAttribute('data-comment-id', comment.id);
    
    // 格式化日期
    const commentDate = new Date(comment.created_at);
    const formattedDate = formatDate(commentDate);
    
    // 获取用户信息
    const user = comment.user || {};
    const username = user.username || '匿名用户';
    const avatarUrl = user.avatar_url || '/assets/images/default-avatar.jpg';
    
    commentElement.innerHTML = `
        <div class="comment-header">
            <div class="comment-user-info">
                <img src="${escapeHTML(avatarUrl)}" 
                     alt="${escapeHTML(username)}" 
                     class="comment-avatar user-avatar" 
                     data-user-id="${user.id || ''}"
                     data-username="${escapeHTML(username)}"
                     style="cursor: pointer;"
                     onerror="this.src='/assets/images/default-avatar.jpg'">
                <span class="comment-username"
                      data-user-id="${user.id || ''}"
                      data-username="${escapeHTML(username)}"
                      style="cursor: pointer;">${escapeHTML(username)}</span>
            </div>
            <div class="comment-date">${formattedDate}</div>
        </div>
        <div class="comment-content">${escapeHTML(comment.content)}</div>
        <div class="comment-actions">
            <!-- 未来可添加的操作按钮 -->
        </div>
    `;
    
    return commentElement;
}

// 格式化日期为易读格式
function formatDate(date) {
    const now = new Date();
    const diffInSeconds = Math.floor((now - date) / 1000);
    
    // 不同时间段显示不同格式
    if (diffInSeconds < 60) {
        return '刚刚';
    } else if (diffInSeconds < 3600) {
        const minutes = Math.floor(diffInSeconds / 60);
        return `${minutes}分钟前`;
    } else if (diffInSeconds < 86400) {
        const hours = Math.floor(diffInSeconds / 3600);
        return `${hours}小时前`;
    } else if (diffInSeconds < 2592000) { // 30天内
        const days = Math.floor(diffInSeconds / 86400);
        return `${days}天前`;
    } else {
        // 超过30天，显示具体日期
        return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    }
}

// HTML转义函数，防止XSS攻击
function escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// 提交评论
async function submitComment(promptId, content) {
    if (!promptId || !content.trim()) return;
    
    // 检查是否已登录
    if (!isLoggedIn()) {
        showToast('请先登录后再发表评论', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/prompts/${promptId}/comments/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeader()  // 添加认证头
            },
            body: JSON.stringify({ 
                content: content
                // 移除user_id，后端会自动使用当前登录用户的ID
            })
        });
        
        if (response.status === 401) {
            showToast('登录状态已过期，请重新登录', 'warning');
            // 清除过期的token
            localStorage.removeItem('promptmarket_token');
            updateLoginState(false);
            return;
        }
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || '提交评论失败');
        }
        
        const newComment = await response.json();
        
        // 更新评论计数
        const commentsCountElement = document.getElementById('comments-count');
        const currentCount = parseInt(commentsCountElement.textContent.match(/\d+/) || 0);
        commentsCountElement.textContent = `(${currentCount + 1})`;
        
        // 重新加载评论列表以获取完整的用户信息
        await loadComments(promptId);
        
        // 清空输入框
        document.getElementById('comment-input').value = '';
        
        showToast('评论发布成功', 'success');
    } catch (error) {
        console.error('提交评论失败:', error);
        showToast(error.message || '评论发布失败，请稍后重试', 'error');
    }
}

// 更新评论表单状态
function updateCommentFormState() {
    const commentForm = document.querySelector('.comment-form');
    const submitBtn = document.getElementById('submit-comment-btn');
    const commentInput = document.getElementById('comment-input');
    
    if (!commentForm || !submitBtn || !commentInput) return;
    
    if (isLoggedIn()) {
        // 已登录状态
        commentInput.disabled = false;
        submitBtn.disabled = false;
        commentInput.placeholder = '在这里输入你的评论...';
        submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> 发表评论';
    } else {
        // 未登录状态
        commentInput.disabled = true;
        submitBtn.disabled = true;
        commentInput.placeholder = '请先登录后再发表评论';
        submitBtn.innerHTML = '<i class="fas fa-lock"></i> 请先登录';
    }
}
