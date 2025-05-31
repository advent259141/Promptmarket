// 私信页面JavaScript

// 全局变量
const API_BASE_URL = (() => {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return `${protocol}//localhost:8000/api/v1`;
    }
    
    return `${protocol}//${hostname}/api/v1`;
})();

let currentUser = null;
let conversations = [];
let notifications = [];
let currentChatUserId = null;
let currentNotificationId = null;
let messages = [];
let unreadCount = 0;
let currentTab = 'private-messages';

// DOM元素
const backBtn = document.getElementById('back-btn');
const logoutBtn = document.getElementById('logout-btn');
const userAvatar = document.getElementById('user-avatar');
const userName = document.getElementById('user-name');

// 标签页元素
const tabBtns = document.querySelectorAll('.tab-btn');
const privateMessagesContent = document.getElementById('private-messages-content');
const notificationsContent = document.getElementById('notifications-content');
const listTitle = document.getElementById('list-title');
const markAllReadBtn = document.getElementById('mark-all-read-btn');

// 标签徽章
const privateMessageBadge = document.getElementById('private-message-badge');
const notificationBadge = document.getElementById('notification-badge');

const conversationsList = document.getElementById('conversations-list');
const notificationsList = document.getElementById('notifications-list');
const noConversations = document.getElementById('no-conversations');
const noNotifications = document.getElementById('no-notifications');
const totalUnreadBadge = document.getElementById('total-unread-badge');
const totalUnreadCount = document.getElementById('total-unread-count');

const chatWelcome = document.getElementById('chat-welcome');
const chatArea = document.getElementById('chat-area');
const notificationDetail = document.getElementById('notification-detail');
const chatUserAvatar = document.getElementById('chat-user-avatar');
const chatUserName = document.getElementById('chat-user-name');
const closeChatBtn = document.getElementById('close-chat-btn');
const closeNotificationBtn = document.getElementById('close-notification-btn');

// 通知详情元素
const notificationTitle = document.getElementById('notification-title');
const notificationType = document.getElementById('notification-type');
const notificationDate = document.getElementById('notification-date');
const notificationContent = document.getElementById('notification-content');

const messagesContainer = document.getElementById('messages-container');
const messageInput = document.getElementById('message-input');
const sendMessageBtn = document.getElementById('send-message-btn');
const charCount = document.getElementById('char-count');
const loadingOverlay = document.getElementById('loading-overlay');

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    initializePrivateMessages();
});

// 初始化私信页面
async function initializePrivateMessages() {
    try {
        showLoading(true);
        
        // 检查用户登录状态
        currentUser = await getCurrentUser();
        if (!currentUser) {
            window.location.href = 'index.html';
            return;
        }
        
        // 更新用户信息显示
        updateUserDisplay();
          // 加载对话列表
        await loadConversations();
        
        // 加载通知列表
        await loadNotifications();
        
        // 加载消息摘要（包含私信和通知的未读数量）
        await loadMessageSummary();
        
        // 绑定事件监听器
        bindEventListeners();
          // 检查URL参数是否指定了特定用户聊天
        const urlParams = new URLSearchParams(window.location.search);
        const userId = urlParams.get('user');
        const username = urlParams.get('username');
        
        if (userId) {
            await openChat(parseInt(userId));
        } else if (username) {
            // 如果只有用户名，需要先通过用户名获取用户ID
            await openChatByUsername(username);
        }
        
    } catch (error) {
        console.error('初始化私信页面失败:', error);
        showToast('加载失败，请刷新页面重试', 'error');
    } finally {
        showLoading(false);
    }
}

// 获取当前用户信息
async function getCurrentUser() {
    const token = localStorage.getItem('promptmarket_token');
    if (!token) {
        return null;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/auth/user/me`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            return await response.json();
        }
        return null;
    } catch (error) {
        console.error('获取用户信息失败:', error);
        return null;
    }
}

// 更新用户信息显示
function updateUserDisplay() {
    if (currentUser) {
        userName.textContent = currentUser.username;
        userAvatar.src = currentUser.avatar_url || '/assets/images/default-avatar.jpg';
    }
}

// 加载对话列表
async function loadConversations() {
    try {
        const token = localStorage.getItem('promptmarket_token');
        const response = await fetch(`${API_BASE_URL}/messages/conversations`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            throw new Error('获取对话列表失败');
        }
        
        conversations = await response.json();
        renderConversations();
        
    } catch (error) {
        console.error('加载对话列表失败:', error);
        showToast('加载对话列表失败', 'error');
    }
}

// 渲染对话列表
function renderConversations() {
    conversationsList.innerHTML = '';
    
    if (conversations.length === 0) {
        noConversations.style.display = 'block';
        return;
    }
    
    noConversations.style.display = 'none';
    
    conversations.forEach(conversation => {
        const conversationElement = createConversationElement(conversation);
        conversationsList.appendChild(conversationElement);
    });
}

// 创建对话列表项元素
function createConversationElement(conversation) {
    const div = document.createElement('div');
    div.className = 'conversation-item';
    div.dataset.userId = conversation.other_user.id;
    
    const avatarSrc = conversation.other_user.avatar_url || '/assets/images/default-avatar.jpg';
    const lastMessage = conversation.latest_message || '还没有消息';
    const timeStr = formatTime(conversation.last_message_at);
      div.innerHTML = `
        <div class="conversation-avatar-wrapper">
            <img class="conversation-avatar" src="${avatarSrc}" alt="${conversation.other_user.username}">
            ${conversation.unread_count > 0 ? 
                `<span class="conversation-unread-dot"></span>` : 
                ''
            }
        </div>
        <div class="conversation-info">
            <h4 class="conversation-name">${conversation.other_user.username}</h4>
            <p class="conversation-last-message">${lastMessage}</p>
        </div>
        <div class="conversation-meta">
            <span class="conversation-time">${timeStr}</span>
            ${conversation.unread_count > 0 ? 
                `<span class="conversation-unread">${conversation.unread_count}</span>` : 
                ''
            }
        </div>
    `;
    
    div.addEventListener('click', () => {
        openChat(conversation.other_user.id);
    });
    
    return div;
}

// 获取用户信息
async function getUserInfo(userId) {
    try {
        const token = localStorage.getItem('promptmarket_token');
        const response = await fetch(`${API_BASE_URL}/user/${userId}/profile`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error('获取用户信息失败');
        }
        
        const userData = await response.json();
        // 只返回用户基本信息
        return userData.user;
    } catch (error) {
        console.error('获取用户信息失败:', error);
        return null;
    }
}

// 打开聊天
async function openChat(userId) {
    try {
        showLoading(true);
        
        // 获取用户信息
        let user = conversations.find(c => c.other_user.id === userId)?.other_user;
        
        if (!user) {
            // 如果在对话列表中找不到，可能是新对话，需要从API获取用户信息
            user = await getUserInfo(userId);
            if (!user) {
                showToast('用户信息不可用', 'error');
                return;
            }
        }
          currentChatUserId = userId;
        
        // 更新聊天头部
        chatUserName.textContent = user.username;
        chatUserAvatar.src = user.avatar_url || '/assets/images/default-avatar.jpg';
        
        // 显示聊天区域
        chatWelcome.style.display = 'none';
        chatArea.style.display = 'flex';
        
        // 加载消息
        await loadMessages(userId);
        
        // 更新对话列表中的选中状态
        updateConversationSelection(userId);
        
        // 滚动到最新消息
        scrollToBottom();
        
    } catch (error) {
        console.error('打开聊天失败:', error);
        showToast('打开聊天失败', 'error');
    } finally {
        showLoading(false);
    }
}

// 通过用户名打开聊天
async function openChatByUsername(username) {
    try {
        showLoading(true);
        
        // 通过用户名获取用户信息
        const token = localStorage.getItem('promptmarket_token');
        const response = await fetch(`${API_BASE_URL}/user/${username}/profile-by-username`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            showToast('用户不存在', 'error');
            return;
        }
        
        const userData = await response.json();
        const user = userData.user;
        
        // 使用获取到的用户ID打开聊天
        await openChat(user.id);
        
    } catch (error) {
        console.error('通过用户名打开聊天失败:', error);
        showToast('打开聊天失败', 'error');
    } finally {
        showLoading(false);
    }
}

// 加载消息
async function loadMessages(userId) {
    try {
        const token = localStorage.getItem('promptmarket_token');
        const response = await fetch(`${API_BASE_URL}/messages/conversation/${userId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            messages = await response.json();
        } else if (response.status === 404) {
            // 新对话，没有消息
            messages = [];
        } else {
            throw new Error('获取消息失败');
        }
        
        renderMessages();
        
        // 重新加载对话列表以更新未读计数
        await loadConversations();
        await loadUnreadCount();
        
    } catch (error) {
        console.error('加载消息失败:', error);
        showToast('加载消息失败', 'error');
    }
}

// 渲染消息
function renderMessages() {
    messagesContainer.innerHTML = '';
    
    messages.forEach(message => {
        const messageElement = createMessageElement(message);
        messagesContainer.appendChild(messageElement);
    });
}

// 创建消息元素
function createMessageElement(message) {    const div = document.createElement('div');
    const isSent = message.sender_id === currentUser.id;
    div.className = `message ${isSent ? 'sent' : 'received'}`;
    
    const avatarSrc = isSent ?        (currentUser.avatar_url || '/assets/images/default-avatar.jpg') : 
        (message.sender.avatar_url || '/assets/images/default-avatar.jpg');
    
    const timeStr = formatTime(message.created_at);
    
    div.innerHTML = `
        <img class="message-avatar" src="${avatarSrc}" alt="头像">
        <div class="message-content">
            <div class="message-bubble">${escapeHtml(message.content)}</div>
            <div class="message-time">${timeStr}</div>
        </div>
    `;
    
    return div;
}

// 发送消息
async function sendMessage() {
    const content = messageInput.value.trim();
    if (!content || !currentChatUserId) {
        return;
    }
      try {
        sendMessageBtn.disabled = true;
        
        const token = localStorage.getItem('promptmarket_token');
        const response = await fetch(`${API_BASE_URL}/messages/send`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                receiver_id: currentChatUserId,
                content: content
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '发送消息失败');
        }
        
        const newMessage = await response.json();
        
        // 清空输入框
        messageInput.value = '';
        updateCharCount();
        
        // 添加新消息到列表
        messages.push(newMessage);
        renderMessages();
        scrollToBottom();
        
        // 重新加载对话列表
        await loadConversations();
        
    } catch (error) {
        console.error('发送消息失败:', error);
        showToast(error.message || '发送消息失败', 'error');
    } finally {
        sendMessageBtn.disabled = false;
    }
}

// 加载未读消息计数
async function loadUnreadCount() {
    try {
        const token = localStorage.getItem('promptmarket_token');
        const response = await fetch(`${API_BASE_URL}/messages/unread-count`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            unreadCount = data.unread_count;
            updateUnreadDisplay();
        }
        
    } catch (error) {
        console.error('获取未读消息计数失败:', error);
    }
}

// 更新未读消息显示
function updateUnreadDisplay() {
    if (unreadCount > 0) {
        totalUnreadBadge.style.display = 'block';
        totalUnreadCount.textContent = unreadCount;
    } else {
        totalUnreadBadge.style.display = 'none';
    }
}

// 更新对话选中状态
function updateConversationSelection(userId) {
    document.querySelectorAll('.conversation-item').forEach(item => {
        item.classList.remove('active');
        if (parseInt(item.dataset.userId) === userId) {
            item.classList.add('active');
        }
    });
}

// 关闭聊天
function closeChat() {
    currentChatUserId = null;
    chatArea.style.display = 'none';
    chatWelcome.style.display = 'flex';
    
    // 取消所有对话的选中状态
    document.querySelectorAll('.conversation-item').forEach(item => {
        item.classList.remove('active');
    });
}

// 绑定事件监听器
function bindEventListeners() {
    // 返回按钮
    backBtn.addEventListener('click', () => {
        window.location.href = 'index.html';
    });
    
    // 退出登录
    logoutBtn.addEventListener('click', logout);
    
    // 关闭聊天
    closeChatBtn.addEventListener('click', closeChat);
    
    // 发送消息
    sendMessageBtn.addEventListener('click', sendMessage);
    
    // 输入框事件
    messageInput.addEventListener('input', () => {
        updateCharCount();
        updateSendButtonState();
        autoResizeTextarea();
    });
      messageInput.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // 标签页切换事件
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            switchTab(btn.dataset.tab);
        });
    });
    
    // 关闭通知详情
    if (closeNotificationBtn) {
        closeNotificationBtn.addEventListener('click', closeNotificationDetail);
    }
    
    // 标记所有已读按钮
    if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', markAllAsRead);
    }
}

// 更新字符计数
function updateCharCount() {
    const length = messageInput.value.length;
    charCount.textContent = length;
    
    if (length > 900) {
        charCount.style.color = 'var(--error-color)';
    } else if (length > 800) {
        charCount.style.color = 'var(--warning-color)';
    } else {
        charCount.style.color = 'var(--text-secondary)';
    }
}

// 更新发送按钮状态
function updateSendButtonState() {
    const hasContent = messageInput.value.trim().length > 0;
    const isValidLength = messageInput.value.length <= 1000;
    sendMessageBtn.disabled = !hasContent || !isValidLength || !currentChatUserId;
}

// 自动调整文本框高度
function autoResizeTextarea() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
}

// 滚动到底部
function scrollToBottom() {
    setTimeout(() => {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }, 100);
}

// 格式化时间
function formatTime(timeString) {
    const time = new Date(timeString);
    const now = new Date();
    const diffInSeconds = (now - time) / 1000;
    
    if (diffInSeconds < 60) {
        return '刚刚';
    } else if (diffInSeconds < 3600) {
        return `${Math.floor(diffInSeconds / 60)}分钟前`;
    } else if (diffInSeconds < 86400) {
        return `${Math.floor(diffInSeconds / 3600)}小时前`;
    } else if (diffInSeconds < 604800) {
        return `${Math.floor(diffInSeconds / 86400)}天前`;
    } else {
        return time.toLocaleDateString();
    }
}

// HTML转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 显示/隐藏加载状态
function showLoading(show) {
    loadingOverlay.style.display = show ? 'flex' : 'none';
}

// 显示toast通知
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// 退出登录
function logout() {
    localStorage.removeItem('promptmarket_token');
    window.location.href = 'index.html';
}

// ============= 通知系统相关函数 =============

// 切换标签页
function switchTab(tabName) {
    currentTab = tabName;
    
    // 更新标签按钮状态
    tabBtns.forEach(btn => {
        if (btn.dataset.tab === tabName) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    // 切换内容区域
    if (tabName === 'private-messages') {
        privateMessagesContent.classList.add('active');
        notificationsContent.classList.remove('active');
        listTitle.innerHTML = '<i class="fas fa-comments"></i> 对话列表';
        markAllReadBtn.style.display = 'none';
    } else if (tabName === 'notifications') {
        privateMessagesContent.classList.remove('active');
        notificationsContent.classList.add('active');
        listTitle.innerHTML = '<i class="fas fa-bell"></i> 通知列表';
        markAllReadBtn.style.display = notifications.filter(n => n.is_read === 0).length > 0 ? 'block' : 'none';
    }
    
    // 关闭当前打开的聊天或通知详情
    closeChat();
    closeNotificationDetail();
}

// 加载通知列表
async function loadNotifications() {
    try {
        const token = localStorage.getItem('promptmarket_token');
        const response = await fetch(`${API_BASE_URL}/messages/notifications?page=1&per_page=50`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            throw new Error('获取通知失败');
        }
        
        const data = await response.json();
        notifications = data.notifications || [];
        
        renderNotifications();
        
    } catch (error) {
        console.error('加载通知失败:', error);
        notifications = [];
        renderNotifications();
    }
}

// 渲染通知列表
function renderNotifications() {
    if (notifications.length === 0) {
        notificationsList.innerHTML = `
            <div class="no-notifications">
                <i class="fas fa-bell-slash"></i>
                <p>暂无通知</p>
                <p class="hint">系统通知将在这里显示</p>
            </div>
        `;
        return;
    }
    
    const notificationElements = notifications.map(notification => 
        createNotificationElement(notification)
    );
    
    notificationsList.innerHTML = notificationElements.join('');
    
    // 绑定点击事件
    notificationsList.querySelectorAll('.notification-item').forEach((item, index) => {
        item.addEventListener('click', () => {
            openNotificationDetail(notifications[index]);
        });
    });
}

// 创建通知列表项元素
function createNotificationElement(notification) {
    const isUnread = notification.is_read === 0;
    const timeStr = formatTime(notification.created_at);
    
    // 根据通知类型选择图标
    let iconClass = 'fas fa-bell';
    switch (notification.notification_type) {
        case 'system':
            iconClass = 'fas fa-cog';
            break;
        case 'admin':
            iconClass = 'fas fa-user-shield';
            break;
        case 'prompt_approved':
            iconClass = 'fas fa-check-circle';
            break;
        case 'prompt_rejected':
            iconClass = 'fas fa-times-circle';
            break;
        case 'prompt_withdrawn':
            iconClass = 'fas fa-undo';
            break;
    }
    
    const typeText = {
        'system': '系统',
        'admin': '管理员',
        'prompt_approved': '审核通过',
        'prompt_rejected': '审核拒绝',
        'prompt_withdrawn': '已撤回'
    }[notification.notification_type] || '通知';
    
    return `
        <div class="notification-item ${isUnread ? 'unread' : ''}" data-notification-id="${notification.id}">
            <div class="notification-icon ${notification.notification_type}">
                <i class="${iconClass}"></i>
            </div>
            <div class="notification-content">
                <div class="notification-header">
                    <h4 class="notification-title">${escapeHtml(notification.title)}</h4>
                    <div class="notification-meta">
                        <span class="notification-type-badge ${notification.notification_type}">${typeText}</span>
                        <span class="notification-date">${timeStr}</span>
                    </div>
                </div>
                <p class="notification-preview">${escapeHtml(notification.content)}</p>
            </div>
        </div>
    `;
}

// 打开通知详情
async function openNotificationDetail(notification) {
    try {
        currentNotificationId = notification.id;
        
        // 更新通知详情显示
        notificationTitle.textContent = notification.title;
        notificationType.textContent = {
            'system': '系统',
            'admin': '管理员',
            'prompt_approved': '审核通过',
            'prompt_rejected': '审核拒绝',
            'prompt_withdrawn': '已撤回'
        }[notification.notification_type] || '通知';
        notificationType.className = `notification-type-badge ${notification.notification_type}`;
        notificationDate.textContent = formatTime(notification.created_at);
        notificationContent.innerHTML = escapeHtml(notification.content).replace(/\n/g, '<br>');
        
        // 显示通知详情，隐藏其他区域
        chatWelcome.style.display = 'none';
        chatArea.style.display = 'none';
        notificationDetail.style.display = 'flex';
        
        // 如果通知未读，标记为已读
        if (notification.is_read === 0) {
            await markNotificationAsRead(notification.id);
        }
        
    } catch (error) {
        console.error('打开通知详情失败:', error);
        showToast('打开通知详情失败', 'error');
    }
}

// 关闭通知详情
function closeNotificationDetail() {
    currentNotificationId = null;
    notificationDetail.style.display = 'none';
    chatWelcome.style.display = 'flex';
}

// 标记通知为已读
async function markNotificationAsRead(notificationId) {
    try {
        const token = localStorage.getItem('promptmarket_token');
        const response = await fetch(`${API_BASE_URL}/messages/notifications/${notificationId}/read`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            // 更新本地通知状态
            const notification = notifications.find(n => n.id === notificationId);
            if (notification) {
                notification.is_read = 1;
                notification.read_at = new Date().toISOString();
            }
            
            // 重新渲染通知列表和更新计数
            renderNotifications();
            await loadMessageSummary();
        }
        
    } catch (error) {
        console.error('标记通知已读失败:', error);
    }
}

// 标记所有通知为已读
async function markAllAsRead() {
    try {
        const token = localStorage.getItem('promptmarket_token');
        
        let url = `${API_BASE_URL}/messages/notifications/mark-all-read`;
        if (currentTab === 'notifications') {
            // 只标记当前标签页的通知为已读
            url += '?notification_type=';
        }
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            // 更新本地通知状态
            notifications.forEach(notification => {
                notification.is_read = 1;
                notification.read_at = new Date().toISOString();
            });
            
            // 重新渲染和更新计数
            renderNotifications();
            await loadMessageSummary();
            
            showToast('所有通知已标记为已读', 'success');
        }
        
    } catch (error) {
        console.error('标记所有已读失败:', error);
        showToast('操作失败，请重试', 'error');
    }
}

// 加载消息摘要（包含私信和通知的未读数量）
async function loadMessageSummary() {
    try {
        const token = localStorage.getItem('promptmarket_token');
        const response = await fetch(`${API_BASE_URL}/messages/summary`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            throw new Error('获取消息摘要失败');
        }
        
        const summary = await response.json();
        
        // 更新各个计数显示
        updateMessageCounts(summary);
        
    } catch (error) {
        console.error('加载消息摘要失败:', error);
        // 如果加载失败，使用之前的方法
        await loadUnreadCount();
    }
}

// 更新消息计数显示
function updateMessageCounts(summary) {
    const { private_message_count, notification_count, total_unread_count } = summary;
    
    // 更新标签徽章
    if (private_message_count > 0) {
        privateMessageBadge.textContent = private_message_count;
        privateMessageBadge.style.display = 'inline';
    } else {
        privateMessageBadge.style.display = 'none';
    }
    
    if (notification_count > 0) {
        notificationBadge.textContent = notification_count;
        notificationBadge.style.display = 'inline';
    } else {
        notificationBadge.style.display = 'none';
    }
    
    // 更新总未读数量
    if (total_unread_count > 0) {
        totalUnreadCount.textContent = total_unread_count;
        totalUnreadBadge.style.display = 'block';
    } else {
        totalUnreadBadge.style.display = 'none';
    }
    
    // 更新标记全部已读按钮的显示
    if (currentTab === 'notifications') {
        markAllReadBtn.style.display = notification_count > 0 ? 'block' : 'none';
    }
}
