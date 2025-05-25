// 处理GitHub登录相关的前端JavaScript代码

// 处理URL中的token参数
document.addEventListener('DOMContentLoaded', function() {
    // 检查URL参数中是否有token
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    
    if (token) {
        // 保存token到localStorage
        localStorage.setItem('promptmarket_token', token);
        
        // 清除URL中的token参数
        const newUrl = window.location.pathname;
        window.history.replaceState({}, document.title, newUrl);
        
        // 更新UI状态为已登录并获取用户信息
        validateToken(token);
    } else {
        // 检查localStorage中是否已有token
        const storedToken = localStorage.getItem('promptmarket_token');
        if (storedToken) {
            // 验证token有效性
            validateToken(storedToken);
        } else {
            // 未登录状态
            updateLoginState(false);
        }
    }
    
    // 初始化登录按钮
    initLoginButtons();
});

// 检查token有效性
async function validateToken(token) {
    try {
        const response = await fetch('/api/v1/auth/user/me', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            // Token有效，用户已登录
            const userData = await response.json();
            updateLoginState(true, userData);
        } else {
            // Token无效，清除存储
            localStorage.removeItem('promptmarket_token');
            updateLoginState(false);
        }
    } catch (error) {
        console.error('验证token时出错:', error);
        updateLoginState(false);
    }
}

// 更新登录状态UI
function updateLoginState(isLoggedIn, userData = null) {
    const loginBtn = document.getElementById('login-btn');
    const userProfileBtn = document.getElementById('user-profile-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const uploadNotice = document.getElementById('upload-notice');
    
    if (isLoggedIn && userData) {
        // 已登录状态
        loginBtn.style.display = 'none';
        userProfileBtn.style.display = 'flex';
        logoutBtn.style.display = 'inline-block';
        
        // 隐藏上传提示
        if (uploadNotice) {
            uploadNotice.classList.add('hidden');
        }
        
        // 更新用户信息显示
        const userAvatar = document.getElementById('user-avatar');
        const userName = document.getElementById('user-name');
        
        if (userAvatar && userData.avatar_url) {
            userAvatar.src = userData.avatar_url;
            userAvatar.alt = userData.username;
            // 添加用户ID和用户名属性，用于点击跳转
            userAvatar.setAttribute('data-user-id', userData.id);
            userAvatar.setAttribute('data-username', userData.username);
            userAvatar.style.cursor = 'pointer';
        }
        
        if (userName) {
            userName.textContent = userData.username;
            // 添加用户ID和用户名属性，用于点击跳转
            userName.setAttribute('data-user-id', userData.id);
            userName.setAttribute('data-username', userData.username);
            userName.style.cursor = 'pointer';
        }
        
        // 初始化站内信功能
        if (typeof initNotificationManager === 'function') {
            initNotificationManager();
        }
    } else {
        // 未登录状态
        loginBtn.style.display = 'inline-block';
        userProfileBtn.style.display = 'none';
        logoutBtn.style.display = 'none';
        
        // 显示上传提示
        if (uploadNotice) {
            uploadNotice.classList.remove('hidden');
        }
        
        // 销毁站内信功能
        if (typeof destroyNotificationManager === 'function') {
            destroyNotificationManager();
        }
    }
    
    // 更新评论表单状态
    if (typeof updateCommentFormState === 'function') {
        updateCommentFormState();
    }
}

// 初始化登录按钮和登录选项
async function initLoginButtons() {
    const loginBtn = document.getElementById('login-btn');
    const logoutBtn = document.getElementById('logout-btn');
    
    if (!loginBtn) return;
    
    // 获取前端配置
    try {
        const configResponse = await fetch('/api/v1/config');
        if (configResponse.ok) {
            const config = await configResponse.json();
            
            // 设置GitHub登录
            if (config.github_login && config.github_login.enabled) {
                // 创建GitHub登录选项
                loginBtn.addEventListener('click', function(e) {
                    e.preventDefault();
                    window.location.href = config.github_login.login_url;
                });
            } else {
                // GitHub登录未启用，可以添加其他登录方式
                loginBtn.addEventListener('click', function(e) {
                    e.preventDefault();
                    alert('登录功能暂未启用');
                });
            }
        }
    } catch (error) {
        console.error('获取配置时出错:', error);
    }
    
    // 设置退出登录功能
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function(e) {
            e.preventDefault();
            // 清除token并更新状态
            localStorage.removeItem('promptmarket_token');
            updateLoginState(false);
        });
    }
}

// 获取授权头
function getAuthHeader() {
    const token = localStorage.getItem('promptmarket_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

// 检查用户是否已登录
function isLoggedIn() {
    return !!localStorage.getItem('promptmarket_token');
}
