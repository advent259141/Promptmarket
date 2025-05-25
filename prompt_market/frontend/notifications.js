// 确保API_BASE_URL已定义
if (typeof API_BASE_URL === 'undefined') {
    // 如果API_BASE_URL未定义，使用默认值
    window.API_BASE_URL = 'http://www.jasongjz.top:8000/api/v1';
    console.warn('API_BASE_URL未定义，使用默认值');
}

// 站内信管理类
class NotificationManager {
    constructor() {
        this.notifications = [];
        this.unreadCount = 0;
        this.isVisible = false;
        this.isLoading = false;
        this.pollingInterval = null;
        this.init();
    }

    init() {
        this.createNotificationUI();
        this.bindEvents();
        this.startPolling();
    }    createNotificationUI() {
        // 先检查是否已经存在通知图标，如果存在就删除
        const existingIcon = document.getElementById('notification-icon');
        if (existingIcon) {
            existingIcon.remove();
        }
        const existingPopup = document.getElementById('notification-popup');
        if (existingPopup) {
            existingPopup.remove();
        }

        // 获取用户信息容器
        const userProfileBtn = document.getElementById('user-profile-btn');
        if (!userProfileBtn) {
            console.warn('User profile button not found, cannot create notification UI');
            return;
        }

        // 创建通知图标
        const notificationIcon = document.createElement('div');
        notificationIcon.className = 'notification-icon';
        notificationIcon.id = 'notification-icon';
        notificationIcon.innerHTML = '<i class="fas fa-bell"></i><span class="notification-badge" id="notification-badge" style="display: none;">0</span>';

        // 创建通知弹窗
        const notificationPopup = document.createElement('div');
        notificationPopup.className = 'notification-popup';
        notificationPopup.id = 'notification-popup';        notificationPopup.innerHTML = `
            <div class="notification-header">
                <h3>站内信</h3>
                <div class="notification-actions">
                    <button id="mark-all-read-btn">
                        <i class="fas fa-check-double"></i>
                        <span>全部已读</span>
                    </button>
                    <button id="delete-read-btn">
                        <i class="fas fa-trash-alt"></i>
                        <span>删除已读</span>
                    </button>
                </div>
            </div>
            <div class="notification-list" id="notification-list">
                <div class="notification-loading">
                    <i class="fas fa-spinner fa-spin"></i>
                    <div>加载中...</div>
                </div>
            </div>
        `;// 插入到用户信息前面
        userProfileBtn.parentNode.insertBefore(notificationIcon, userProfileBtn);
        
        // 添加弹窗到通知图标容器内
        notificationIcon.appendChild(notificationPopup);
        
        console.log('Notification UI created successfully');
    }    bindEvents() {
        const notificationIcon = document.getElementById('notification-icon');
        const notificationPopup = document.getElementById('notification-popup');
        const markAllReadBtn = document.getElementById('mark-all-read-btn');
        const deleteReadBtn = document.getElementById('delete-read-btn');

        if (!notificationIcon) {
            console.warn('Notification icon not found for event binding');
            return;
        }

        console.log('Binding notification events...');

        // 点击图标切换显示状态
        notificationIcon.addEventListener('click', (e) => {
            e.stopPropagation();
            console.log('Notification icon clicked');
            this.togglePopup();
        });

        // 点击外部关闭弹窗
        document.addEventListener('click', (e) => {
            if (!notificationPopup.contains(e.target) && !notificationIcon.contains(e.target)) {
                this.hidePopup();
            }
        });

        // 阻止弹窗内部点击事件冒泡
        notificationPopup.addEventListener('click', (e) => {
            e.stopPropagation();
        });

        // 全部已读按钮
        markAllReadBtn?.addEventListener('click', () => {
            this.markAllAsRead();
        });

        // 删除已读按钮
        deleteReadBtn?.addEventListener('click', () => {
            this.deleteReadNotifications();
        });
    }    async startPolling() {
        // 清理之前的轮询（如果存在）
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
        }
        
        // 立即检查一次
        await this.checkUnreadCount();
        
        // 每30秒检查一次未读数量
        this.pollingInterval = setInterval(() => {
            this.checkUnreadCount();
        }, 30000);
    }

    async checkUnreadCount() {
        try {
            const response = await fetch(`${API_BASE_URL}/notifications/unread-count`, {
                headers: this.getAuthHeaders()
            });

            if (response.ok) {
                const data = await response.json();
                this.updateUnreadCount(data.unread_count);
            }
        } catch (error) {
            console.error('检查未读数量失败:', error);
        }
    }    updateUnreadCount(count) {
        this.unreadCount = count;
        const badge = document.getElementById('notification-badge');
        
        if (badge) {
            if (count > 0) {
                badge.textContent = count > 99 ? '99+' : count.toString();
                badge.style.display = 'flex';
            } else {
                badge.style.display = 'none';
            }
        }
    }

    // updateBadge是updateUnreadCount的别名
    updateBadge() {
        this.updateUnreadCount(this.unreadCount);
    }async togglePopup() {
        console.log('togglePopup called, isVisible:', this.isVisible);
        if (this.isVisible) {
            this.hidePopup();
        } else {
            await this.showPopup();
        }
    }    async showPopup() {
        const popup = document.getElementById('notification-popup');
        if (!popup) {
            console.warn('Notification popup not found');
            return;
        }

        console.log('Showing notification popup');
        this.isVisible = true;
        popup.classList.add('show');
        
        // 加载通知列表
        await this.loadNotifications();
    }

    hidePopup() {
        const popup = document.getElementById('notification-popup');
        if (!popup) {
            console.warn('Notification popup not found for hiding');
            return;
        }

        console.log('Hiding notification popup');
        this.isVisible = false;
        popup.classList.remove('show');
    }

    async loadNotifications() {
        if (this.isLoading) return;
        
        this.isLoading = true;
        const list = document.getElementById('notification-list');
        
        try {
            const response = await fetch(`${API_BASE_URL}/notifications?limit=20`, {
                headers: this.getAuthHeaders()
            });

            if (response.ok) {
                this.notifications = await response.json();
                this.renderNotifications();
            } else {
                throw new Error('加载失败');
            }
        } catch (error) {
            console.error('加载通知失败:', error);
            list.innerHTML = `
                <div class="notification-empty">
                    <i class="fas fa-exclamation-triangle"></i>
                    <div>加载失败，请重试</div>
                </div>
            `;
        } finally {
            this.isLoading = false;
        }
    }

    renderNotifications() {
        const list = document.getElementById('notification-list');
        
        if (this.notifications.length === 0) {
            list.innerHTML = `
                <div class="notification-empty">
                    <i class="fas fa-inbox"></i>
                    <div>暂无站内信</div>
                </div>
            `;
            return;
        }

        const html = this.notifications.map(notification => `
            <div class="notification-item ${notification.is_read ? '' : 'unread'}" 
                 data-id="${notification.id}"
                 onclick="notificationManager.handleNotificationClick(${notification.id})">
                <div class="notification-title">
                    ${this.escapeHtml(notification.title)}
                    <span class="notification-type ${notification.notification_type}">
                        ${this.getTypeLabel(notification.notification_type)}
                    </span>
                </div>
                <div class="notification-content">
                    ${this.escapeHtml(notification.content)}
                </div>
                <div class="notification-time">
                    ${this.formatTime(notification.created_at)}
                </div>
            </div>
        `).join('');

        list.innerHTML = html;
    }    async handleNotificationClick(notificationId) {
        const notification = this.notifications.find(n => n.id === notificationId);
        if (!notification) return;

        // 如果是未读状态，标记为已读
        if (!notification.is_read) {
            await this.markAsRead(notificationId);
        }

        // 如果有相关的Prompt ID，跳转到Prompt详情
        if (notification.related_id && (notification.notification_type.startsWith('prompt_') || notification.notification_type === 'new_comment')) {
            this.hidePopup();
            // 触发显示Prompt详情
            if (typeof showPromptDetails === 'function') {
                showPromptDetails(notification.related_id);
            }
        }
    }

    async markAsRead(notificationId) {
        try {
            const response = await fetch(`${API_BASE_URL}/notifications/${notificationId}/read`, {
                method: 'PUT',
                headers: this.getAuthHeaders()
            });

            if (response.ok) {
                // 更新本地状态
                const notification = this.notifications.find(n => n.id === notificationId);
                if (notification) {
                    notification.is_read = 1;
                    notification.read_at = new Date().toISOString();
                }
                
                // 重新渲染
                this.renderNotifications();
                
                // 更新未读数量
                this.updateUnreadCount(Math.max(0, this.unreadCount - 1));
            }
        } catch (error) {
            console.error('标记已读失败:', error);
        }
    }

    async markAllAsRead() {
        try {
            const response = await fetch(`${API_BASE_URL}/notifications/mark-all-read`, {
                method: 'PUT',
                headers: this.getAuthHeaders()
            });

            if (response.ok) {
                const data = await response.json();
                
                // 更新本地状态
                this.notifications.forEach(n => {
                    n.is_read = 1;
                    n.read_at = new Date().toISOString();
                });
                
                // 重新渲染
                this.renderNotifications();
                
                // 更新未读数量
                this.updateUnreadCount(0);
                
                showToast(`已标记${data.affected_count}条站内信为已读`, 'success');
            }
        } catch (error) {
            console.error('批量标记已读失败:', error);
            showToast('操作失败，请重试', 'error');
        }
    }

    async deleteReadNotifications() {
        try {
            const response = await fetch(`${API_BASE_URL}/notifications/delete-read`, {
                method: 'DELETE',
                headers: this.getAuthHeaders()
            });

            if (response.ok) {
                const data = await response.json();
                
                // 从本地列表中移除已读通知
                this.notifications = this.notifications.filter(n => !n.is_read);
                
                // 重新渲染
                this.renderNotifications();
                
                showToast(`已删除${data.deleted_count}条已读站内信`, 'success');
            }
        } catch (error) {
            console.error('删除已读通知失败:', error);
            showToast('操作失败，请重试', 'error');
        }
    }    getAuthHeaders() {
        const token = localStorage.getItem('promptmarket_token');
        return {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        };
    }    getTypeLabel(type) {
        const labels = {
            'prompt_approved': '通过',
            'prompt_rejected': '拒绝',
            'prompt_reverted': '撤回',
            'new_comment': '评论',
            'system': '系统'
        };
        return labels[type] || '通知';
    }

    formatTime(timeString) {
        const time = new Date(timeString);
        const now = new Date();
        const diff = now - time;
        
        if (diff < 60000) { // 1分钟内
            return '刚刚';
        } else if (diff < 3600000) { // 1小时内
            return `${Math.floor(diff / 60000)}分钟前`;
        } else if (diff < 86400000) { // 1天内
            return `${Math.floor(diff / 3600000)}小时前`;
        } else {
            return time.toLocaleDateString('zh-CN');
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 显示/隐藏通知功能（根据登录状态）
    show() {
        const icon = document.getElementById('notification-icon');
        if (icon) {
            icon.style.display = 'inline-block';
            this.checkUnreadCount();
        }
    }

    hide() {
        const icon = document.getElementById('notification-icon');
        const popup = document.getElementById('notification-popup');
        if (icon) icon.style.display = 'none';
        if (popup) popup.classList.remove('show');
        this.isVisible = false;
    }
}

// 全局通知管理器实例
let notificationManager = null;

// 初始化通知管理器（在用户登录后调用）
function initNotificationManager() {
    console.log('Initializing notification manager...');
    if (!notificationManager) {
        notificationManager = new NotificationManager();
        console.log('New notification manager created');
    } else {
        // 如果管理器已存在，重新创建UI（防止DOM清理后丢失）
        console.log('Recreating notification UI...');
        notificationManager.createNotificationUI();
        notificationManager.bindEvents();
    }
    notificationManager.show();
    
    // 暴露为全局变量以便测试
    window.notificationManager = notificationManager;
    
    console.log('Notification manager initialized');
}

// 销毁通知管理器（在用户登出后调用）
function destroyNotificationManager() {
    if (notificationManager) {
        notificationManager.hide();
        // 清理DOM元素
        const icon = document.getElementById('notification-icon');
        const popup = document.getElementById('notification-popup');
        if (icon) icon.remove();
        if (popup) popup.remove();
        // 停止轮询
        if (notificationManager.pollingInterval) {
            clearInterval(notificationManager.pollingInterval);
        }
    }
}
