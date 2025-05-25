// 聊天试用功能的JavaScript代码
let chatWindow = null;
let currentConversationId = null;
let isChatting = false;
let currentPromptTitle = "";

// 初始化聊天窗口
function initChatFeature() {
    // 创建聊天窗口DOM
    createChatWindowDOM();
    
    // 获取DOM元素
    chatWindow = document.getElementById('chat-window');
    
    // 添加关闭按钮事件
    document.getElementById('chat-close').addEventListener('click', closeChatWindow);
    
    // 添加发送消息按钮事件
    document.getElementById('chat-send').addEventListener('click', sendMessage);
    
    // 添加输入框回车发送事件
    document.getElementById('chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            sendMessage();
        }
    });
}

// 创建聊天窗口DOM结构
function createChatWindowDOM() {
    // 如果已经存在，则不重复创建
    if (document.getElementById('chat-window')) {
        return;
    }
    
    const chatWindowHTML = `
        <div id="chat-window" class="chat-window">
            <div class="chat-container">
                <div class="chat-header">
                    <h3 class="chat-title">正在试用: <span id="chat-prompt-title"></span></h3>
                    <button id="chat-close" class="chat-close"><i class="fas fa-times"></i></button>
                </div>
                <div id="chat-messages" class="chat-messages">
                    <div id="chat-welcome" class="ai-message chat-message">
                        <p>您好！我是基于当前prompt训练的AI助手。请随意与我交流，看看prompt的效果如何。</p>
                        <span class="message-time">系统消息</span>
                    </div>
                </div>
                <div class="chat-input">
                    <input type="text" id="chat-input" placeholder="输入消息..." />
                    <button id="chat-send">发送</button>
                </div>
            </div>
        </div>
    `;
    
    // 将聊天窗口添加到页面
    document.body.insertAdjacentHTML('beforeend', chatWindowHTML);
}

// 打开聊天窗口
function openChatWindow(promptId, promptTitle) {
    // 检查用户是否已登录
    const token = localStorage.getItem('promptmarket_token');
    if (!token) {
        showLoginRequiredModal();
        return;
    }
    
    // 如果promptTitle没有传入，使用当前保存的标题
    if (!promptTitle && window.currentPromptTitle) {
        promptTitle = window.currentPromptTitle;
    }
    
    // 设置当前prompt信息
    currentPromptId = promptId;
    currentPromptTitle = promptTitle || '未知Prompt';
    
    // 生成对话ID
    currentConversationId = `prompt_${promptId}_${Date.now()}`;
    
    // 更新聊天窗口标题
    document.getElementById('chat-prompt-title').textContent = promptTitle;
    
    // 清空之前的消息
    const messagesContainer = document.getElementById('chat-messages');
    messagesContainer.innerHTML = `
        <div id="chat-welcome" class="ai-message chat-message">
            <p>您好！我是基于当前prompt训练的AI助手。请随意与我交流，看看prompt的效果如何。</p>
            <span class="message-time">系统消息</span>
        </div>
    `;
    
    // 禁止背景滚动
    document.body.style.overflow = 'hidden';
    
    // 显示聊天窗口
    chatWindow.classList.add('show');
    
    // 聚焦到输入框
    setTimeout(() => {
        document.getElementById('chat-input').focus();
    }, 300);
}

// 关闭聊天窗口
function closeChatWindow() {
    // 隐藏聊天窗口
    chatWindow.classList.remove('show');
    
    // 恢复背景滚动
    document.body.style.overflow = '';
    
    // 清除对话历史（后端API调用）
    if (currentConversationId) {
        const token = localStorage.getItem('promptmarket_token');
        if (token) {
            fetch(`${API_BASE_URL}/chat/${currentConversationId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            }).catch(error => console.error('清除对话历史失败:', error));
        }
    }
    
    // 重置对话ID
    currentConversationId = null;
    currentPromptId = null;
}

// 发送消息
async function sendMessage() {
    // 获取输入框的值
    const inputElement = document.getElementById('chat-input');
    const message = inputElement.value.trim();
    
    // 如果消息为空，则不发送
    if (!message || isChatting) return;
    
    // 清空输入框
    inputElement.value = '';
    
    // 添加用户消息到聊天窗口
    addMessage(message, 'user');
    
    // 标记正在聊天中
    isChatting = true;
    
    // 禁用发送按钮，显示加载状态
    toggleSendButton(false);
    
    try {
        // 获取token
        const token = localStorage.getItem('promptmarket_token');
        if (!token) {
            throw new Error('未登录');
        }
        
        // 发送请求到后端
        const response = await fetch(`${API_BASE_URL}/chat/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                prompt_id: currentPromptId,
                message: message
            })
        });
        
        // 检查响应状态
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '请求失败');
        }
        
        // 解析响应数据
        const data = await response.json();
        
        // 添加AI回复到聊天窗口
        addMessage(data.response, 'ai');
        
    } catch (error) {
        console.error('发送消息失败:', error);
        
        // 显示错误消息
        addSystemMessage(`发送失败: ${error.message}`);
    } finally {
        // 恢复发送按钮状态
        toggleSendButton(true);
        isChatting = false;
    }
}

// 添加消息到聊天窗口
function addMessage(text, role) {
    const messagesContainer = document.getElementById('chat-messages');
    const time = new Date().toLocaleTimeString();
    
    const messageElement = document.createElement('div');
    messageElement.className = `chat-message ${role}-message`;
    
    // 将文本中的换行符转换为<br>标签
    const formattedText = text.replace(/\n/g, '<br>');
    
    messageElement.innerHTML = `
        <p>${formattedText}</p>
        <span class="message-time">${time}</span>
    `;
    
    // 添加渐入动画
    messageElement.style.opacity = '0';
    messagesContainer.appendChild(messageElement);

    // 强制重绘以应用初始不透明度，然后触发动画
    requestAnimationFrame(() => {
        messageElement.style.transition = 'opacity 0.3s ease-in-out';
        messageElement.style.opacity = '1';
    });
    
    // 滚动到底部
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// 添加系统消息
function addSystemMessage(text) {
    const messagesContainer = document.getElementById('chat-messages');
    const time = new Date().toLocaleTimeString();
    
    const messageElement = document.createElement('div');
    messageElement.className = 'chat-message system-message';
    messageElement.innerHTML = `
        <p><i class="fas fa-info-circle"></i> ${text}</p>
        <span class="message-time">系统消息 ${time}</span>
    `;
    
    messagesContainer.appendChild(messageElement);
    
    // 滚动到底部
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// 切换发送按钮状态
function toggleSendButton(enabled) {
    const sendButton = document.getElementById('chat-send');
    if (enabled) {
        sendButton.disabled = false;
        sendButton.innerHTML = '发送';
    } else {
        sendButton.disabled = true;
        sendButton.innerHTML = '<span class="chat-loader"></span>';
    }
}

// 显示需要登录的提示模态框
function showLoginRequiredModal() {
    // 如果已有模态框，先移除
    const existingModal = document.getElementById('login-modal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // 创建模态框
    const modalElement = document.createElement('div');
    modalElement.className = 'modal';
    modalElement.id = 'login-modal';
    modalElement.style.display = 'block';
    
    modalElement.innerHTML = `
        <div class="modal-content" style="max-width: 450px; animation: modalFadeIn 0.3s;">
            <span class="close">&times;</span>
            <div class="login-required">
                <h3><i class="fas fa-lock"></i> 需要登录</h3>
                <p>您需要登录后才能使用聊天试用功能。</p>
                <button id="login-redirect-btn" class="action-btn"><i class="fas fa-sign-in-alt"></i> 立即登录</button>
            </div>
        </div>
    `;
    
    // 添加到页面
    document.body.appendChild(modalElement);
    
    // 添加关闭事件
    modalElement.querySelector('.close').addEventListener('click', () => {
        modalElement.remove();
    });
    
    // 点击登录按钮
    document.getElementById('login-redirect-btn').addEventListener('click', () => {
        // 触发顶部的登录按钮
        document.getElementById('login-btn').click();
        modalElement.remove();
    });
}

// 在页面加载完成后初始化聊天功能
document.addEventListener('DOMContentLoaded', function() {
    initChatFeature();
});
