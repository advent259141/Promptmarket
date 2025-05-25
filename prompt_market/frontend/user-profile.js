/**
 * 用户主页功能的JavaScript代码
 * 负责处理用户主页的显示、导航和数据加载
 */

// 确保API_BASE_URL已定义
if (typeof API_BASE_URL === 'undefined') {
    // 如果API_BASE_URL未定义，使用默认值
    window.API_BASE_URL = 'http://www.jasongjz.top:8000/api/v1';
    console.warn('API_BASE_URL未定义，使用默认值');
}

// 用户主页相关变量
let currentUserProfileData = null;
let isUserProfileLoading = false;
let currentLoggedInUser = null; // 存储当前登录用户信息

/**
 * 初始化用户主页功能
 */
function initUserProfileFeature() {
    // 添加用户头像点击事件监听器
    setupUserAvatarClickHandlers();
    
    // 监听浏览器前进后退按钮
    window.addEventListener('popstate', handlePopState);
    
    // 初始化时获取当前用户信息
    fetchCurrentUser();
    
    // 检查页面加载时是否需要显示用户主页
    checkInitialUserProfileRoute();
}

/**
 * 设置用户头像点击事件处理器
 */
function setupUserAvatarClickHandlers() {
    // 为页面中所有的用户头像添加点击事件
    document.addEventListener('click', function(event) {
        const target = event.target;
        
        // 检查是否点击的是用户头像或包含用户信息的元素
        if (target.classList.contains('user-avatar') || 
            target.classList.contains('author-avatar') ||
            target.closest('.user-info') ||
            target.closest('.author-info')) {
            
            event.preventDefault();
            
            // 获取用户ID或用户名
            const userId = target.getAttribute('data-user-id') || 
                          target.closest('[data-user-id]')?.getAttribute('data-user-id');
            const username = target.getAttribute('data-username') || 
                           target.closest('[data-username]')?.getAttribute('data-username');
            
            if (userId || username) {
                navigateToUserProfile(userId, username);
            }
        }
    });
    
    // 为右上角的用户资料按钮添加特殊处理
    const userProfileBtn = document.getElementById('user-profile-btn');
    if (userProfileBtn) {
        userProfileBtn.addEventListener('click', function(event) {
            // 如果点击的是退出按钮，不处理
            if (event.target.id === 'logout-btn' || event.target.closest('#logout-btn')) {
                return;
            }
            
            event.preventDefault();
            
            // 获取当前登录用户信息
            const token = localStorage.getItem('promptmarket_token');
            if (token) {
                // 获取当前用户信息然后跳转
                getCurrentUserAndNavigate();
            }
        });
    }
}

/**
 * 获取当前用户信息并跳转到主页
 */
async function getCurrentUserAndNavigate() {
    try {
        // 如果已经有用户信息，直接使用
        if (currentLoggedInUser) {
            navigateToUserProfile(currentLoggedInUser.id, currentLoggedInUser.username);
            return;
        }
        
        const token = localStorage.getItem('promptmarket_token');
        if (!token) {
            console.warn('用户未登录');
            return;
        }
        
        const response = await fetch(`${API_BASE_URL}/auth/user/me`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const userData = await response.json();
            // 更新全局变量
            currentLoggedInUser = userData;
            navigateToUserProfile(userData.id, userData.username);
        } else {
            console.error('获取用户信息失败:', response.status);
        }
    } catch (error) {
        console.error('获取当前用户信息时出错:', error);
    }
}

/**
 * 检查初始路由是否为用户主页
 */
function checkInitialUserProfileRoute() {
    const hash = window.location.hash;
    const userMatch = hash.match(/^#\/user\/(.+)$/);
    
    if (userMatch) {
        const identifier = userMatch[1];
        // 检查是否为数字（用户ID）
        if (/^\d+$/.test(identifier)) {
            loadUserProfile(parseInt(identifier), null);
        } else {
            loadUserProfile(null, identifier);
        }
    }
}

/**
 * 处理浏览器前进后退
 */
function handlePopState(event) {
    const hash = window.location.hash;
    
    if (!hash || hash === '#' || hash === '#/') {
        // 返回主页
        showMainPage();
    } else {
        // 检查是否为用户主页路由
        checkInitialUserProfileRoute();
    }
}

/**
 * 导航到用户主页
 * @param {number|null} userId - 用户ID
 * @param {string|null} username - 用户名
 */
function navigateToUserProfile(userId, username) {
    // 更新URL
    const identifier = userId || username;
    window.history.pushState({}, '', `#/user/${identifier}`);
    
    // 加载用户主页
    loadUserProfile(userId, username);
}

/**
 * 加载用户主页数据
 * @param {number|null} userId - 用户ID
 * @param {string|null} username - 用户名
 */
async function loadUserProfile(userId, username) {    if (isUserProfileLoading) {
        return;
    }
    
    isUserProfileLoading = true;
    
    try {
        // 显示加载状态
        showUserProfileLoadingState();
        
        // 先获取当前登录用户信息
        await fetchCurrentUser();
          // 构建API URL
        let apiUrl;
        if (userId) {
            apiUrl = `${API_BASE_URL}/user/${userId}/profile`;
        } else if (username) {
            apiUrl = `${API_BASE_URL}/user/${username}/profile-by-username`;
        } else {
            console.error('Missing both userId and username');
            throw new Error('缺少用户ID或用户名');
        }
        
        // 获取认证头
        const headers = {
            'Content-Type': 'application/json'
        };
        
        const token = localStorage.getItem('promptmarket_token');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        
        // 发起API请求
        const response = await fetch(apiUrl, {
            method: 'GET',
            headers: headers
        });
        
        if (!response.ok) {
            if (response.status === 404) {
                showUserProfileNotFound();
                return;
            } else if (response.status === 401) {
                showUserProfileUnauthorized();
                return;
            } else {
                throw new Error(`API请求失败: ${response.status}`);
            }
        }
        
        const userData = await response.json();
        currentUserProfileData = userData;
        
        // 渲染用户主页
        renderUserProfile(userData);
        
    } catch (error) {
        console.error('加载用户主页时出错:', error);
        showUserProfileError(error.message);
    } finally {
        isUserProfileLoading = false;
    }
}

/**
 * 显示用户主页加载状态
 */
function showUserProfileLoadingState() {
    const mainContainer = document.querySelector('main') || document.body;
    mainContainer.innerHTML = `
        <div class="user-profile-page">
            <div class="loading-spinner">
                <div class="spinner"></div>
            </div>
        </div>
    `;
}

/**
 * 显示用户未找到页面
 */
function showUserProfileNotFound() {
    const mainContainer = document.querySelector('main') || document.body;
    mainContainer.innerHTML = `
        <div class="user-profile-page">
            <a href="#" class="back-button" onclick="showMainPage()">
                <i class="fas fa-arrow-left"></i>
                返回主页
            </a>
            <div class="empty-state">
                <i class="fas fa-user-slash"></i>
                <h3>用户不存在</h3>
                <p>抱歉，找不到该用户的信息。</p>
            </div>
        </div>
    `;
}

/**
 * 显示未授权页面
 */
function showUserProfileUnauthorized() {
    const mainContainer = document.querySelector('main') || document.body;
    mainContainer.innerHTML = `
        <div class="user-profile-page">
            <a href="#" class="back-button" onclick="showMainPage()">
                <i class="fas fa-arrow-left"></i>
                返回主页
            </a>
            <div class="empty-state">
                <i class="fas fa-lock"></i>
                <h3>需要登录</h3>
                <p>请先登录后再查看用户主页。</p>
            </div>
        </div>
    `;
}

/**
 * 显示用户主页错误状态
 */
function showUserProfileError(message) {
    const mainContainer = document.querySelector('main') || document.body;
    mainContainer.innerHTML = `
        <div class="user-profile-page">
            <a href="#" class="back-button" onclick="showMainPage()">
                <i class="fas fa-arrow-left"></i>
                返回主页
            </a>
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>加载失败</h3>
                <p>加载用户主页时出现错误：${message}</p>
            </div>
        </div>
    `;
}

/**
 * 渲染用户主页
 * @param {Object} userData - 用户数据
 */
function renderUserProfile(userData) {
    const { user, prompts, stats } = userData;
    
    // 格式化加入日期
    const joinDate = new Date(user.created_at || Date.now()).toLocaleDateString('zh-CN');
    
    // 获取用户头像
    const avatarUrl = user.avatar_url || 
        `data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">👤</text></svg>`;
      const mainContainer = document.querySelector('main') || document.body;
    mainContainer.innerHTML = `
        <div class="user-profile-page">
            <a href="#" class="back-button" onclick="showMainPage()">
                <i class="fas fa-arrow-left"></i>
                返回主页
            </a>
            
            <div class="user-info-card">
                <div class="user-header">
                    <img src="${escapeHTML(avatarUrl)}" 
                         alt="${escapeHTML(user.username)}" 
                         class="user-avatar-large"
                         onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>👤</text></svg>'">
                    
                    <div class="user-basic-info">
                        <h1>${escapeHTML(user.username)}</h1>
                        <div class="user-join-date">
                            <i class="fas fa-calendar-alt"></i>
                            加入时间：${joinDate}
                        </div>
                    </div>
                </div>
                
                <div class="user-stats">
                    <div class="stat-item">
                        <span class="stat-number">${stats.total_prompts}</span>
                        <span class="stat-label">发布的Prompt</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-number">${stats.total_likes}</span>
                        <span class="stat-label">获得的赞</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-number">${stats.total_views}</span>
                        <span class="stat-label">总浏览量</span>
                    </div>
                </div>
            </div>              <div class="content-tabs">
                <button class="tab-button active" onclick="switchTab('prompts')">
                    <i class="fas fa-lightbulb"></i>
                    ${isOwnProfile() ? '我的Prompt' : 'TA的Prompt'}
                </button>
                ${isOwnProfile() ? `
                <button class="tab-button" onclick="switchTab('comments')">
                    <i class="fas fa-comments"></i>
                    我的评论
                </button>
                ` : ''}
            </div>
            
            <div class="content-section active" id="prompts-section">
                <div class="user-prompts-section">
                    ${renderUserPrompts(prompts)}
                </div>
            </div>
            
            ${isOwnProfile() ? `
            <div class="content-section" id="comments-section">
                <div class="user-comments-section">
                    <div class="loading-spinner">
                        <div class="spinner"></div>
                    </div>
                </div>
            </div>
            ` : ''}
        </div>
    `;
}

/**
 * 渲染用户的Prompt列表
 * @param {Array} prompts - Prompt列表
 */
function renderUserPrompts(prompts) {
    if (!prompts || prompts.length === 0) {
        return `
            <div class="empty-state">
                <i class="fas fa-inbox"></i>
                <h3>暂无发布的Prompt</h3>
                <p>${isOwnProfile() ? '您还没有发布任何Prompt。' : '该用户还没有发布任何Prompt。'}</p>
            </div>
        `;
    }
    
    const promptsHtml = prompts.map((prompt, index) => {
        // 限制描述长度
        const description = prompt.description ? 
            (prompt.description.length > 100 ? 
                prompt.description.substring(0, 100) + '...' : 
                prompt.description) : 
            '暂无描述';
        
        // 格式化日期
        const createdDate = new Date(prompt.created_at).toLocaleDateString('zh-CN');
        
        // 获取状态信息
        let statusBadge = '';
        let statusClass = '';
        if (isOwnProfile()) {
            switch (prompt.status) {
                case 0:
                    statusBadge = '<span class="status-badge pending">审核中</span>';
                    statusClass = 'status-pending';
                    break;
                case 1:
                    statusBadge = '<span class="status-badge approved">已通过</span>';
                    statusClass = 'status-approved';
                    break;
                case 2:
                    statusBadge = '<span class="status-badge rejected">已拒绝</span>';
                    statusClass = 'status-rejected';
                    break;
                default:
                    statusBadge = '<span class="status-badge unknown">未知状态</span>';
                    statusClass = 'status-unknown';
            }
        }
        
        // 渲染标签
        const tagsHtml = prompt.tags && prompt.tags.length > 0 ? 
            `<div class="card-tags">${prompt.tags.map(tag => `<span class="tag-badge">${escapeHTML(tag.name)}</span>`).join('')}</div>` : 
            '';
        
        // 操作按钮 - 只有在自己的资料页面才显示
        const actionsHtml = isOwnProfile() ? `
            <div class="prompt-actions">
                <button class="action-btn edit-btn" onclick="editUserPrompt(${prompt.id})">
                    <i class="fas fa-edit"></i> 编辑
                </button>
                <button class="action-btn delete-btn" onclick="deleteUserPrompt(${prompt.id})">
                    <i class="fas fa-trash"></i> 删除
                </button>
            </div>
        ` : '';
        
        return `
            <div class="prompt-card ${statusClass}" data-prompt-id="${prompt.id}">
                <div class="card-header">
                    <h3>${escapeHTML(prompt.title)} ${prompt.is_r18 ? '<span class="r18-badge">R18</span>' : ''}</h3>
                    ${statusBadge}
                </div>
                <p>${escapeHTML(description)}</p>
                ${tagsHtml}
                <div class="card-stats">
                    <span>${createdDate}</span>
                    <span><i class="fas fa-thumbs-up"></i> ${prompt.likes}</span>
                    <span><i class="fas fa-thumbs-down"></i> ${prompt.dislikes || 0}</span>
                    <span class="views-count"><i class="fas fa-eye"></i> ${prompt.views || 0}</span>
                </div>
                ${actionsHtml}
            </div>
        `;
    }).join('');
    
    return `<div class="user-prompts-grid">${promptsHtml}</div>`;
}

/**
 * 切换标签页
 * @param {string} tab - 标签页类型: 'prompts' 或 'comments'
 */
function switchTab(tab) {
    // 更新按钮状态
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[onclick="switchTab('${tab}')"]`).classList.add('active');
    
    // 更新内容区域
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById(`${tab}-section`).classList.add('active');
      // 如果切换到评论标签页且还没有加载评论，则加载评论
    if (tab === 'comments' && isOwnProfile()) {
        const commentsSection = document.querySelector('.user-comments-section');
        if (commentsSection && commentsSection.querySelector('.loading-spinner')) {
            loadUserComments();
        }
    }
}

/**
 * 加载用户评论
 */
async function loadUserComments() {
    try {
        // 确保只有当前登录用户才能加载评论
        if (!isOwnProfile()) {
            throw new Error('只能查看自己的评论');
        }
        
        const userId = getCurrentUserId();
        if (!userId) {
            throw new Error('无法获取用户ID');
        }
        
        const response = await fetch(`${API_BASE_URL}/users/${userId}/comments`);
        
        if (!response.ok) {
            throw new Error('加载评论失败');
        }
        
        const comments = await response.json();
        renderUserComments(comments);
    } catch (error) {
        console.error('加载用户评论失败:', error);
        document.querySelector('.user-comments-section').innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>加载失败</h3>
                <p>无法加载评论数据，请稍后重试。</p>
            </div>
        `;
    }
}

/**
 * 渲染用户评论列表
 * @param {Array} comments - 评论列表
 */
function renderUserComments(comments) {
    const commentsSection = document.querySelector('.user-comments-section');
    
    if (!comments || comments.length === 0) {
        const isOwn = isOwnProfile();
        commentsSection.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-comment-slash"></i>
                <h3>暂无评论</h3>
                <p>${isOwn ? '您还没有发表过任何评论。' : 'TA还没有发表过任何评论。'}</p>
            </div>
        `;
        return;
    }
    
    const commentsHtml = comments.map(comment => {
        const createdDate = new Date(comment.created_at).toLocaleDateString('zh-CN');
        const createdTime = new Date(comment.created_at).toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        return `
            <div class="comment-card" data-comment-id="${comment.id}">
                <div class="comment-header">
                    <a href="#" class="comment-prompt-title" onclick="openPromptDetail(${comment.prompt_id})">
                        ${escapeHTML(comment.prompt_title || '未知Prompt')}
                    </a>
                    <span class="comment-date">${createdDate} ${createdTime}</span>
                </div>
                <div class="comment-content">
                    ${escapeHTML(comment.content)}
                </div>
                <div class="comment-actions">
                    <button class="delete-comment-btn" onclick="deleteUserComment(${comment.id})">
                        <i class="fas fa-trash"></i> 删除
                    </button>
                </div>
            </div>
        `;
    }).join('');
    
    commentsSection.innerHTML = commentsHtml;
}

/**
 * 获取当前用户ID
 * 从用户资料页面的数据中获取用户ID
 */
function getCurrentUserId() {
    // 首先尝试从当前用户资料数据中获取用户ID
    if (currentUserProfileData && currentUserProfileData.user) {
        return currentUserProfileData.user.id;
    }
    
    // 从URL参数中获取用户ID（假设用户资料页面URL包含用户ID）
    const urlParams = new URLSearchParams(window.location.search);
    const userId = urlParams.get('userId');
    
    if (userId) {
        return parseInt(userId);
    }
    
    // 最后尝试从全局变量获取当前登录用户的ID
    if (currentLoggedInUser) {
        return currentLoggedInUser.id;
    }
    
    return null;
}

/**
 * 判断当前查看的用户资料是否为当前登录用户自己的资料
 * @returns {boolean} 是否为当前登录用户的资料
 */
function isOwnProfile() {
    // 从全局变量获取当前登录用户信息
    if (!currentLoggedInUser) {
        return false; // 未登录或尚未获取用户信息
    }
    
    // 获取当前正在查看的用户资料ID
    const profileUserId = currentUserProfileData?.user?.id;
    
    // 如果两者都存在且相等，则为用户自己的资料
    return currentLoggedInUser && profileUserId && currentLoggedInUser.id === profileUserId;
}

/**
 * 获取当前登录用户信息
 */
async function fetchCurrentUser() {
    const token = localStorage.getItem('promptmarket_token');
    if (!token) {
        currentLoggedInUser = null;
        return null;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/auth/user/me`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            currentLoggedInUser = await response.json();
            return currentLoggedInUser;
        } else {
            currentLoggedInUser = null;
            return null;
        }
    } catch (error) {
        console.error('获取当前用户信息失败:', error);
        currentLoggedInUser = null;
        return null;
    }
}

/**
 * 在用户主页中打开Prompt详情（复用现有逻辑）
 * @param {number} promptId - Prompt ID
 */
function openPromptDetail(promptId) {
    // 复用现有的openPromptDetails函数
    if (typeof openPromptDetails === 'function') {
        openPromptDetails(promptId);
    } else if (typeof openModal === 'function') {
        openModal(promptId);
    } else {
        console.error('openPromptDetails或openModal函数未定义');
        // 备用方案：直接跳转到主页并显示详情
        showMainPage();
        setTimeout(() => {
            if (typeof openPromptDetails === 'function') {
                openPromptDetails(promptId);
            }
        }, 500);
    }
}

/**
 * 删除用户评论
 * @param {number} commentId - 评论ID
 */
async function deleteUserComment(commentId) {
    if (!confirm('确定要删除这条评论吗？此操作无法撤销。')) {
        return;
    }
    
    try {
        // 检查是否已登录
        if (!isLoggedIn()) {
            showToast('请先登录', 'warning');
            return;
        }
        
        const response = await fetch(`${API_BASE_URL}/comments/${commentId}`, {
            method: 'DELETE',
            headers: {
                ...getAuthHeader()
            }
        });
        
        if (response.status === 401) {
            showToast('登录状态已过期，请重新登录', 'warning');
            localStorage.removeItem('promptmarket_token');
            updateLoginState(false);
            return;
        }
        
        if (response.status === 403) {
            showToast('您没有权限删除此评论', 'error');
            return;
        }
        
        if (!response.ok) {
            throw new Error('删除评论失败');
        }
        
        // 从DOM中移除评论卡片
        const commentCard = document.querySelector(`[data-comment-id="${commentId}"]`);
        if (commentCard) {
            commentCard.remove();
        }
          // 检查是否还有评论，如果没有则显示空状态
        const remainingComments = document.querySelectorAll('.comment-card').length;
        if (remainingComments === 0) {
            const commentsSection = document.querySelector('.user-comments-section');
            const isOwn = isOwnProfile();
            commentsSection.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-comment-slash"></i>
                    <h3>暂无评论</h3>
                    <p>${isOwn ? '您还没有发表过任何评论。' : 'TA还没有发表过任何评论。'}</p>
                </div>
            `;
        }
        
        showToast('评论已删除', 'success');
        
    } catch (error) {
        console.error('删除评论失败:', error);
        showToast('删除评论失败，请稍后重试', 'error');
    }
}

/**
 * 编辑用户Prompt
 * @param {number} promptId - Prompt ID
 */
async function editUserPrompt(promptId) {
    try {
        const token = localStorage.getItem('promptmarket_token');
        if (!token) {
            showToast('请先登录', 'error');
            return;
        }
        
        // 获取Prompt详细信息 - 使用新的编辑专用端点
        const response = await fetch(`${API_BASE_URL}/prompts/${promptId}/edit`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            if (response.status === 403) {
                throw new Error('您没有权限编辑此Prompt');
            } else if (response.status === 404) {
                throw new Error('Prompt不存在');
            } else {
                throw new Error('获取Prompt信息失败');
            }
        }
        
        const prompt = await response.json();
        
        // 显示编辑模态框
        showEditPromptModal(prompt);
        
    } catch (error) {
        console.error('获取Prompt信息失败:', error);
        showToast(error.message || '获取Prompt信息失败，请稍后重试', 'error');
    }
}

/**
 * 删除用户Prompt
 * @param {number} promptId - Prompt ID
 */
async function deleteUserPrompt(promptId) {
    if (!confirm('确定要删除这个Prompt吗？此操作无法撤销。')) {
        return;
    }
    
    try {
        const token = localStorage.getItem('promptmarket_token');
        if (!token) {
            showToast('请先登录', 'error');
            return;
        }
        
        const response = await fetch(`${API_BASE_URL}/prompts/${promptId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.status === 403) {
            showToast('您没有权限删除此Prompt', 'error');
            return;
        }
        
        if (!response.ok) {
            throw new Error('删除Prompt失败');
        }
        
        // 从DOM中移除Prompt卡片
        const promptCard = document.querySelector(`[data-prompt-id="${promptId}"]`);
        if (promptCard) {
            promptCard.remove();
        }
        
        // 检查是否还有Prompt，如果没有则显示空状态
        const remainingPrompts = document.querySelectorAll('.prompt-card').length;
        if (remainingPrompts === 0) {
            const promptsSection = document.querySelector('.user-prompts-section');
            promptsSection.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <h3>暂无发布的Prompt</h3>
                    <p>您还没有发布任何Prompt。</p>
                </div>
            `;
        }
        
        showToast('Prompt已删除', 'success');
        
    } catch (error) {
        console.error('删除Prompt失败:', error);
        showToast('删除Prompt失败，请稍后重试', 'error');
    }
}

// 全局变量存储当前编辑的Prompt信息
let currentEditingPrompt = null;
let currentUserTags = []; // 用于存储当前编辑的标签

/**
 * 显示编辑Prompt模态框
 * @param {Object} prompt - Prompt对象
 */
function showEditPromptModal(prompt) {
    currentEditingPrompt = prompt;
    currentUserTags = prompt.tags ? prompt.tags.map(tag => tag.name) : [];
    
    // 创建模态框HTML并添加到页面
    const modalHtml = `
        <div id="editPromptModal" class="edit-modal">
            <div class="edit-modal-content">
                <div class="edit-modal-header">
                    <h3>编辑Prompt</h3>
                    <button class="edit-modal-close" onclick="closeEditPromptModal()">&times;</button>
                </div>
                <div class="edit-modal-body">
                    <form id="editPromptForm">
                        <div class="form-group">
                            <label for="editTitle">标题</label>
                            <input type="text" id="editTitle" class="form-control" value="${escapeHTML(prompt.title)}" required>
                        </div>
                        <div class="form-group">
                            <label for="editDescription">描述</label>
                            <textarea id="editDescription" class="form-control" rows="2">${escapeHTML(prompt.description || '')}</textarea>
                        </div>
                        <div class="form-group">
                            <label for="editContent">内容</label>
                            <textarea id="editContent" class="form-control" rows="8" required>${escapeHTML(prompt.content)}</textarea>
                        </div>
                        <div class="form-group">
                            <label for="editTags">标签 (按回车添加，最多5个)</label>
                            <div class="tags-input-container">
                                <input type="text" id="editTags" class="form-control" placeholder="输入标签后按回车添加...">
                                <div class="tags-container" id="editTagsContainer"></div>
                            </div>
                            <small class="tags-help">已添加 <span id="editTagsCount">${currentUserTags.length}</span>/5 个标签</small>
                        </div>
                        <div class="form-group r18-option">
                            <label>内容分级</label>
                            <div class="r18-toggle">
                                <input type="checkbox" id="editIsR18" ${prompt.is_r18 ? 'checked' : ''}>
                                <label for="editIsR18">这是R18内容</label>
                            </div>
                            <small class="r18-help">编辑后的Prompt需要重新审核</small>
                        </div>
                    </form>
                </div>
                <div class="edit-modal-footer">
                    <button type="button" class="btn-secondary" onclick="closeEditPromptModal()">取消</button>
                    <button type="button" class="btn-primary" onclick="savePromptChanges()">保存更改</button>
                </div>
            </div>
        </div>
    `;
    
    // 添加模态框到body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
      // 显示模态框
    const modal = document.getElementById('editPromptModal');
    modal.style.display = 'flex';
    
    // 初始化标签功能
    initEditTagsInput();
    renderEditTags();
    
    // 点击模态框外部关闭
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeEditPromptModal();
        }
    });
}

/**
 * 关闭编辑Prompt模态框
 */
function closeEditPromptModal() {
    const modal = document.getElementById('editPromptModal');
    if (modal) {
        modal.remove();
    }
    currentEditingPrompt = null;
    currentUserTags = [];
}

/**
 * 初始化编辑标签输入功能
 */
function initEditTagsInput() {
    const tagsInput = document.getElementById('editTags');
    if (tagsInput) {
        tagsInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const tagValue = tagsInput.value.trim();
                
                if (currentUserTags.length >= 5) {
                    showToast('最多只能添加5个标签', 'warning');
                    return;
                }
                
                if (currentUserTags.includes(tagValue)) {
                    showToast('标签已存在', 'warning');
                    return;
                }
                
                if (tagValue) {
                    currentUserTags.push(tagValue);
                    renderEditTags();
                    tagsInput.value = '';
                }
            }
        });
    }
}

/**
 * 渲染编辑标签
 */
function renderEditTags() {
    const tagsContainer = document.getElementById('editTagsContainer');
    const tagsCount = document.getElementById('editTagsCount');
    
    if (tagsContainer) {
        tagsContainer.innerHTML = '';
        currentUserTags.forEach((tag, index) => {
            const tagElement = document.createElement('div');
            tagElement.className = 'tag';
            tagElement.innerHTML = `
                <span>${escapeHTML(tag)}</span>
                <button type="button" onclick="removeEditTag(${index})">
                    <i class="fas fa-times"></i>
                </button>
            `;
            tagsContainer.appendChild(tagElement);
        });
    }
    
    if (tagsCount) {
        tagsCount.textContent = currentUserTags.length;
    }
}

/**
 * 移除编辑标签
 * @param {number} index - 标签索引
 */
function removeEditTag(index) {
    currentUserTags.splice(index, 1);
    renderEditTags();
}

/**
 * 保存Prompt更改
 */
async function savePromptChanges() {
    try {
        const token = localStorage.getItem('promptmarket_token');
        if (!token) {
            showToast('请先登录', 'error');
            return;
        }
        
        // 获取表单数据
        const title = document.getElementById('editTitle').value.trim();
        const description = document.getElementById('editDescription').value.trim();
        const content = document.getElementById('editContent').value.trim();
        const isR18 = document.getElementById('editIsR18').checked;
        
        // 验证表单
        if (!title || !content) {
            showToast('标题和内容不能为空', 'error');
            return;
        }
        
        const updatedPrompt = {
            title: title,
            description: description,
            content: content,
            tags: currentUserTags,
            is_r18: isR18 ? 1 : 0
        };
        
        // 发送更新请求
        const response = await fetch(`${API_BASE_URL}/prompts/${currentEditingPrompt.id}`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(updatedPrompt)
        });
        
        if (response.status === 403) {
            showToast('您没有权限编辑此Prompt', 'error');
            return;
        }
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '更新失败');
        }        showToast('Prompt已更新，正在重新审核中', 'success');
        closeEditPromptModal();
          // 重新加载用户资料页面
        if (currentUserProfileData && currentUserProfileData.user) {
            // 重新加载当前用户的资料页面
            const userId = currentUserProfileData.user.id;
            const username = currentUserProfileData.user.username;
            
            // 确保参数有效
            if (userId || username) {
                loadUserProfile(userId, username);
            } else {                console.error('Invalid user data for reload');
                // 更新当前编辑的Prompt卡片状态
                updatePromptCardAfterEdit(currentEditingPrompt.id);
            }
        } else {
            // 如果没有当前用户数据，尝试从URL重新加载
            const hash = window.location.hash;
            if (hash && hash.includes('/user/')) {
                checkInitialUserProfileRoute();
            } else {
                // 作为最后的备用方案，更新当前Prompt卡片
                updatePromptCardAfterEdit(currentEditingPrompt.id);
            }
        }
        
    } catch (error) {
        console.error('保存Prompt更改失败:', error);
        showToast(`保存失败: ${error.message}`, 'error');
    }
}

/**
 * 更新编辑后的Prompt卡片状态（备用方案）
 * @param {number} promptId - Prompt ID
 */
function updatePromptCardAfterEdit(promptId) {
    // 查找对应的Prompt卡片
    const promptCard = document.querySelector(`[data-prompt-id="${promptId}"]`);
    if (promptCard) {
        // 查找状态标记元素
        const statusBadge = promptCard.querySelector('.status-badge');
        if (statusBadge) {
            // 更新为审核中状态
            statusBadge.className = 'status-badge pending';
            statusBadge.textContent = '审核中';
        }
        
        // 添加闪烁动画提示用户已更新
        promptCard.style.animation = 'flash 0.5s ease-in-out';
        setTimeout(() => {
            promptCard.style.animation = '';
        }, 500);
    }
}

/**
 * 简单的Toast通知函数
 * @param {string} message - 消息内容
 * @param {string} type - 消息类型: 'success', 'error', 'warning'
 */
function showToast(message, type = 'info') {
    // 创建toast元素
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    // 添加样式
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 5px;
        color: white;
        font-weight: 500;
        z-index: 10000;
        opacity: 0;
        transform: translateX(100%);
        transition: all 0.3s ease;
    `;
    
    // 根据类型设置背景色
    switch (type) {
        case 'success':
            toast.style.backgroundColor = '#28a745';
            break;
        case 'error':
            toast.style.backgroundColor = '#dc3545';
            break;
        case 'warning':
            toast.style.backgroundColor = '#ffc107';
            toast.style.color = '#000';
            break;
        default:
            toast.style.backgroundColor = '#17a2b8';
    }
    
    // 添加到页面
    document.body.appendChild(toast);
    
    // 显示动画
    setTimeout(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(0)';
    }, 100);
    
    // 自动消失
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

/**
 * 返回主页，隐藏用户配置文件页面
 */
function showMainPage() {
    // 清除当前URL hash
    window.history.pushState({}, '', window.location.pathname);
    
    // 获取主容器
    const mainContainer = document.querySelector('main') || document.body;
    
    // 清除用户配置文件页面内容
    const userProfilePage = mainContainer.querySelector('.user-profile-page');
    if (userProfilePage) {
        userProfilePage.remove();
    }
    
    // 恢复原始的主页内容（如果还不存在）
    if (!document.getElementById('browse-section')) {
        location.reload(); // 如果主页内容不存在，重新加载页面
        return;
    }
    
    // 确保主页内容可见
    const browseSection = document.getElementById('browse-section');
    const uploadSection = document.getElementById('upload-section');
    
    if (browseSection && uploadSection) {
        // 显示主页导航和内容
        const browseBtn = document.getElementById('browse-btn');
        const uploadBtn = document.getElementById('upload-btn');
        
        if (browseBtn && uploadBtn) {
            // 恢复正常的页面布局
            browseSection.style.display = '';
            uploadSection.style.display = '';
            
            // 激活浏览页面
            if (typeof setActivePage === 'function') {
                setActivePage('browse');
            } else {
                // 备用方案：手动设置活跃状态
                browseBtn.classList.add('active');
                uploadBtn.classList.remove('active');
                browseSection.classList.add('active-section');
                uploadSection.classList.remove('active-section');
            }
        }
    }
    
    // 重置用户配置文件相关状态
    currentUserProfileData = null;
    isUserProfileLoading = false;
    
    // 如果存在加载Prompt函数，重新加载数据
    if (typeof loadPrompts === 'function') {
        loadPrompts(1); // 重新加载第一页的数据
    }
}

// 页面加载完成后初始化用户主页功能
document.addEventListener('DOMContentLoaded', function() {
    initUserProfileFeature();
});
