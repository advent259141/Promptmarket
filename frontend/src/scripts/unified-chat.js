// 统一聊天试用功能的JavaScript代码

// 确保API_BASE_URL已定义
if (typeof API_BASE_URL === 'undefined') {
    // 动态获取API基础URL，自动适应协议
    window.API_BASE_URL = (() => {
        const protocol = window.location.protocol;
        const hostname = window.location.hostname;
        
        // 如果是localhost或127.0.0.1，使用带端口的地址
        if (hostname === 'localhost' || hostname === '127.0.0.1') {
            return `${protocol}//localhost:8000/api/v1`;
        }
        
        // 否则使用当前域名（通过反向代理）
        return `${protocol}//${hostname}/api/v1`;
    })();
    console.warn('API_BASE_URL未定义，使用动态生成的默认值:', window.API_BASE_URL);
}

let chatWindow = null;
let currentSessionId = null;
let isChatting = false;
let currentPromptTitle = "";
let unifiedChatPromptId = null;
let availableModels = [];
let currentModelType = "gemini";

// 初始化聊天功能
function initUnifiedChatFeature() {
    // 创建聊天窗口DOM
    createUnifiedChatWindowDOM();
    
    // 获取DOM元素
    chatWindow = document.getElementById('unified-chat-window');
    
    // 添加关闭按钮事件
    document.getElementById('unified-chat-close').addEventListener('click', closeUnifiedChatWindow);
    
    // 添加发送消息按钮事件
    document.getElementById('unified-chat-send').addEventListener('click', sendUnifiedMessage);
    
    // 添加输入框回车发送事件
    document.getElementById('unified-chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            sendUnifiedMessage();
        }
    });
    
    // 加载可用模型
    loadAvailableModels();
}

// 创建聊天窗口DOM结构
function createUnifiedChatWindowDOM() {
    // 如果已经存在，则不重复创建
    if (document.getElementById('unified-chat-window')) {
        return;
    }
      const chatWindowHTML = `
        <div id="unified-chat-window" class="chat-window">
            <div class="chat-container">
                <div class="chat-header">
                    <div>
                        <h3 class="chat-title">正在试用: <span id="unified-chat-prompt-title"></span></h3>
                        <div class="model-selector">
                            <label for="model-select">AI模型:</label>
                            <select id="model-select" class="model-select">
                                <option value="gemini">Gemini (加载中...)</option>
                            </select>
                        </div>
                    </div>
                    <button id="unified-chat-close" class="chat-close"><i class="fas fa-times"></i></button>
                </div>
                <div id="unified-chat-messages" class="chat-messages">
                    <div id="unified-chat-welcome" class="ai-message chat-message">
                        <p>您好！我是基于当前prompt训练的AI助手。请选择您想要使用的AI模型，然后随意与我交流，看看prompt的效果如何。</p>
                        <span class="message-time">系统消息</span>
                    </div>
                </div>
                <div class="chat-input">
                    <input type="text" id="unified-chat-input" placeholder="输入消息..." />
                    <button id="unified-chat-send">发送</button>
                </div>
            </div>
        </div>
    `;
      // 将聊天窗口添加到页面
    document.body.insertAdjacentHTML('beforeend', chatWindowHTML);
    
    // 添加模型选择事件
    document.getElementById('model-select').addEventListener('change', (e) => {
        currentModelType = e.target.value;
        
        // 如果已有会话，重新开始新会话
        if (currentSessionId) {
            currentSessionId = null;
            addUnifiedSystemMessage(`已切换到 ${getModelDisplayName(currentModelType)}，开始新对话`);
        }
    });
}

// 加载可用模型
async function loadAvailableModels() {
    try {
        const response = await fetch(`${API_BASE_URL}/chat-models`);
        if (response.ok) {
            const data = await response.json();
            availableModels = data.models || [];
            updateModelSelector();
        }
    } catch (error) {
        console.error('加载可用模型失败:', error);
        // 使用默认模型
        availableModels = [{
            type: "gemini",
            name: "Gemini (默认)",
            description: "Google 的 Gemini 模型"
        }];
        updateModelSelector();
    }
}

// 更新模型选择器
function updateModelSelector() {
    const modelSelect = document.getElementById('model-select');
    if (!modelSelect) return;
    
    modelSelect.innerHTML = '';
    
    if (availableModels.length === 0) {
        modelSelect.innerHTML = '<option value="">暂无可用模型</option>';
        modelSelect.disabled = true;
        return;
    }
    
    availableModels.forEach(model => {
        const option = document.createElement('option');
        option.value = model.type;
        option.textContent = model.name;
        option.title = model.description;
        modelSelect.appendChild(option);
    });
    
    // 设置默认选中第一个可用模型
    if (availableModels.length > 0) {
        currentModelType = availableModels[0].type;
        modelSelect.value = currentModelType;
        modelSelect.disabled = false;
    }
}

// 获取模型显示名称
function getModelDisplayName(modelType) {
    const model = availableModels.find(m => m.type === modelType);
    return model ? model.name : modelType;
}

// 打开聊天窗口
function openUnifiedChatWindow(promptId, promptTitle) {
    // 检查用户是否已登录
    const token = localStorage.getItem('promptmarket_token');
    if (!token) {
        showUnifiedLoginRequiredModal();
        return;
    }
    
    // 检查是否有可用模型
    if (availableModels.length === 0) {
        showUnifiedErrorModal('暂无可用的AI模型，请联系管理员配置API密钥');
        return;
    }
    
    // 如果promptTitle没有传入，使用当前保存的标题
    if (!promptTitle && window.currentPromptTitle) {
        promptTitle = window.currentPromptTitle;
    }
      // 设置当前prompt信息
    unifiedChatPromptId = promptId;
    currentPromptTitle = promptTitle || '未知Prompt';
    
    // 重置会话ID
    currentSessionId = null;
    
    // 更新聊天窗口标题
    document.getElementById('unified-chat-prompt-title').textContent = promptTitle;
      // 清空之前的消息
    const messagesContainer = document.getElementById('unified-chat-messages');
    messagesContainer.innerHTML = `
        <div id="unified-chat-welcome" class="ai-message chat-message">
            <p>您好！我是基于当前prompt训练的AI助手。请选择您想要使用的AI模型，然后随意与我交流，看看prompt的效果如何。</p>
            <span class="message-time">系统消息</span>
        </div>
    `;
    
    // 禁止背景滚动
    document.body.style.overflow = 'hidden';
    
    // 显示聊天窗口
    chatWindow.classList.add('show');
      // 聚焦到输入框
    setTimeout(() => {
        document.getElementById('unified-chat-input').focus();
    }, 300);
}

// 关闭聊天窗口
function closeUnifiedChatWindow() {
    // 隐藏聊天窗口
    chatWindow.classList.remove('show');
    
    // 恢复背景滚动
    document.body.style.overflow = '';
    
    // 清除对话历史（后端API调用）
    if (currentSessionId) {
        const token = localStorage.getItem('promptmarket_token');
        if (token) {
            fetch(`${API_BASE_URL}/unified-chat/${currentSessionId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            }).catch(error => console.error('清除对话历史失败:', error));
        }
    }
      // 重置会话信息
    currentSessionId = null;
    unifiedChatPromptId = null;
}

// 发送消息
async function sendUnifiedMessage() {
    // 获取输入框的值
    const inputElement = document.getElementById('unified-chat-input');
    const message = inputElement.value.trim();
    
    // 如果消息为空，则不发送
    if (!message || isChatting) return;
    
    // 检查是否有可用模型
    if (availableModels.length === 0) {
        addUnifiedSystemMessage('暂无可用的AI模型，请联系管理员配置API密钥');
        return;
    }
    
    // 清空输入框
    inputElement.value = '';
    
    // 添加用户消息到聊天窗口
    addUnifiedMessage(message, 'user');
      // 标记正在聊天中
    isChatting = true;
      // 禁用发送按钮，显示加载状态
    toggleUnifiedSendButton(false);
    
    try {
        // 获取token
        const token = localStorage.getItem('promptmarket_token');
        if (!token) {
            throw new Error('未登录');
        }
        
        // 构建请求数据
        const requestData = {
            message: message,
            model_type: currentModelType
        };
          // 如果是新会话，添加prompt_id
        if (!currentSessionId) {
            requestData.prompt_id = unifiedChatPromptId;
        } else {
            requestData.session_id = currentSessionId;
        }
        
        // 发送请求到后端
        const response = await fetch(`${API_BASE_URL}/unified-chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(requestData)
        });
        
        // 检查响应状态
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '请求失败');
        }
        
        // 解析响应数据
        const data = await response.json();
        
        // 更新会话ID
        currentSessionId = data.session_id;        // 添加AI回复到聊天窗口
        const modelDisplayName = getModelDisplayName(data.model_type);
        addUnifiedMessage(data.message, 'ai', modelDisplayName);
          } catch (error) {
        console.error('发送消息失败:', error);
        
        // 显示错误消息
        addUnifiedSystemMessage(`发送失败: ${error.message}`);
    } finally {
        // 恢复发送按钮状态
        toggleUnifiedSendButton(true);
        isChatting = false;
    }
}

// 添加消息到聊天窗口
function addUnifiedMessage(text, role, modelName = null) {
    const messagesContainer = document.getElementById('unified-chat-messages');
    const time = new Date().toLocaleTimeString();
    
    const messageElement = document.createElement('div');
    messageElement.className = `chat-message ${role}-message`;
    
    // 将文本中的换行符转换为<br>标签
    const formattedText = text.replace(/\n/g, '<br>');
    
    // 为AI消息添加模型标识
    const modelLabel = role === 'ai' && modelName ? ` (${modelName})` : '';
    
    messageElement.innerHTML = `
        <p>${formattedText}</p>
        <span class="message-time">${time}${modelLabel}</span>
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
function addUnifiedSystemMessage(text) {
    const messagesContainer = document.getElementById('unified-chat-messages');
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
function toggleUnifiedSendButton(enabled) {
    const sendButton = document.getElementById('unified-chat-send');
    if (enabled) {
        sendButton.disabled = false;
        sendButton.innerHTML = '发送';
    } else {
        sendButton.disabled = true;
        sendButton.innerHTML = '<span class="chat-loader"></span>';
    }
}

// 显示需要登录的提示模态框
function showUnifiedLoginRequiredModal() {
    showUnifiedErrorModal('您需要登录后才能使用聊天试用功能。', '需要登录', true);
}

// 显示错误模态框
function showUnifiedErrorModal(message, title = '错误', showLoginBtn = false) {
    // 如果已有模态框，先移除
    const existingModal = document.getElementById('unified-error-modal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // 创建模态框
    const modalElement = document.createElement('div');
    modalElement.className = 'modal';
    modalElement.id = 'unified-error-modal';
    modalElement.style.display = 'block';
    
    const loginButton = showLoginBtn ? 
        `<button id="unified-login-redirect-btn" class="action-btn"><i class="fas fa-sign-in-alt"></i> 立即登录</button>` : '';
    
    modalElement.innerHTML = `
        <div class="modal-content" style="max-width: 450px; animation: modalFadeIn 0.3s;">
            <span class="close">&times;</span>
            <div class="login-required">
                <h3><i class="fas fa-${showLoginBtn ? 'lock' : 'exclamation-triangle'}"></i> ${title}</h3>
                <p>${message}</p>
                ${loginButton}
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
    if (showLoginBtn) {
        const loginBtn = document.getElementById('unified-login-redirect-btn');
        if (loginBtn) {
            loginBtn.addEventListener('click', () => {
                // 触发顶部的登录按钮
                const topLoginBtn = document.getElementById('login-btn');
                if (topLoginBtn) {
                    topLoginBtn.click();
                }
                modalElement.remove();
            });
        }
    }
}

// 在页面加载完成后初始化聊天功能
document.addEventListener('DOMContentLoaded', function() {
    initUnifiedChatFeature();
});

// 全局函数，供其他脚本调用
window.openUnifiedChatWindow = openUnifiedChatWindow;