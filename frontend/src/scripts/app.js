// 全局变量
// 动态获取API基础URL，自动适应协议
const API_BASE_URL = (() => {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    
    // 如果是localhost或127.0.0.1，使用带端口的地址
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return `${protocol}//localhost:8000/api/v1`;
    }
    
    // 否则使用当前域名（通过反向代理）
    return `${protocol}//${hostname}/api/v1`;
})();
let currentPage = 1;
const ITEMS_PER_PAGE = 16; // 每页16个prompt (4行，每行4个)
let currentPromptId = null;
let currentSearchTerm = ""; // 当前搜索关键词
let currentTagFilter = ""; // 当前标签筛选
let currentSortBy = 'upload_time_desc'; // 默认排序方式更改为"上传时间 (新到老)"
let currentR18Filter = "all"; // R18筛选: "all"-所有内容, "non-r18"-仅非R18, "r18-only"-仅R18

// 路由相关变量
let isInitialLoad = true; // 标记是否为初始加载

// DOM元素
const browseBtn = document.getElementById('browse-btn');
const uploadBtn = document.getElementById('upload-btn');
const browseSection = document.getElementById('browse-section');
const uploadSection = document.getElementById('upload-section');
const promptGrid = document.getElementById('prompt-grid');
const loading = document.getElementById('loading');
const prevPageBtn = document.getElementById('prev-page');
const nextPageBtn = document.getElementById('next-page');
const currentPageSpan = document.getElementById('current-page');
const modal = document.getElementById('prompt-modal');
const closeBtn = document.querySelector('.close');
const uploadForm = document.getElementById('upload-form');
const searchBtn = document.getElementById('search-btn');
const searchInput = document.getElementById('search-input');
const clearSearchBtn = document.getElementById('clear-search');
const tagsFilterList = document.getElementById('filter-tags-list');
const sortBySelect = document.getElementById('sort-by-select');
const r18FilterSelect = document.getElementById('r18-filter-select'); // 新增: R18筛选下拉框
const contactUsBtn = document.getElementById('contact-us-btn');
const contactUsPopup = document.getElementById('contact-us-popup');
const loginBtn = document.getElementById('login-btn');
const userProfileBtn = document.getElementById('user-profile-btn');
const logoutBtn = document.getElementById('logout-btn');

/**
 * 初始化路由功能
 */
function initRouting() {
    // 监听浏览器前进后退按钮
    window.addEventListener('popstate', handleRouteChange);
    
    // 检查页面加载时的路由
    checkInitialRoute();
}

/**
 * 检查初始路由
 */
function checkInitialRoute() {
    const hash = window.location.hash;
    
    // 解析URL参数
    const params = parseRouteParams();
    
    if (params.page) {
        currentPage = parseInt(params.page) || 1;
    }
    
    if (params.search) {
        currentSearchTerm = decodeURIComponent(params.search);
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.value = currentSearchTerm;
        }
    }
    
    if (params.tag) {
        currentTagFilter = decodeURIComponent(params.tag);
    }
    
    if (params.sort) {
        currentSortBy = params.sort;
        const sortSelect = document.getElementById('sort-by-select');
        if (sortSelect) {
            sortSelect.value = currentSortBy;
        }
    }
    
    if (params.r18) {
        currentR18Filter = params.r18;
        const r18Select = document.getElementById('r18-filter-select');
        if (r18Select) {
            r18Select.value = currentR18Filter;
        }
    }
}

/**
 * 解析URL中的路由参数
 */
function parseRouteParams() {
    const hash = window.location.hash;
    const params = {};
    
    if (hash) {
        // 解析类似 #/page=1&search=test&tag=技术&sort=upload_time_desc&r18=all 的格式
        const paramString = hash.substring(2); // 移除 '#/'
        const pairs = paramString.split('&');
        
        pairs.forEach(pair => {
            const [key, value] = pair.split('=');
            if (key && value) {
                params[key] = value;
            }
        });
    }
    
    return params;
}

/**
 * 更新URL以反映当前状态
 */
function updateURL() {
    if (isInitialLoad) {
        // 初始加载时不更新URL，避免破坏从URL解析的参数
        return;
    }
    
    const params = [];
    
    // 添加页码
    if (currentPage > 1) {
        params.push(`page=${currentPage}`);
    }
    
    // 添加搜索词
    if (currentSearchTerm) {
        params.push(`search=${encodeURIComponent(currentSearchTerm)}`);
    }
    
    // 添加标签筛选
    if (currentTagFilter) {
        params.push(`tag=${encodeURIComponent(currentTagFilter)}`);
    }
    
    // 添加排序方式（仅在非默认时添加）
    if (currentSortBy && currentSortBy !== 'upload_time_desc') {
        params.push(`sort=${currentSortBy}`);
    }
    
    // 添加R18筛选（仅在非默认时添加）
    if (currentR18Filter && currentR18Filter !== 'all') {
        params.push(`r18=${currentR18Filter}`);
    }
    
    // 构建新的URL
    const newHash = params.length > 0 ? `#/${params.join('&')}` : '#/';
    
    // 更新URL但不触发页面跳转
    if (window.location.hash !== newHash) {
        window.history.pushState(null, '', newHash);
    }
}

/**
 * 处理路由变化（浏览器前进后退）
 */
function handleRouteChange() {
    // 解析新的URL参数
    const params = parseRouteParams();
    
    // 更新状态变量
    const newPage = parseInt(params.page) || 1;
    const newSearch = params.search ? decodeURIComponent(params.search) : '';
    const newTag = params.tag ? decodeURIComponent(params.tag) : '';
    const newSort = params.sort || 'upload_time_desc';
    const newR18 = params.r18 || 'all';
    
    // 检查是否有变化
    let hasChanged = false;
    
    if (currentPage !== newPage) {
        currentPage = newPage;
        hasChanged = true;
    }
    
    if (currentSearchTerm !== newSearch) {
        currentSearchTerm = newSearch;
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.value = currentSearchTerm;
        }
        hasChanged = true;
    }
    
    if (currentTagFilter !== newTag) {
        currentTagFilter = newTag;
        // 更新标签筛选UI
        updateTagFilterUI();
        hasChanged = true;
    }
    
    if (currentSortBy !== newSort) {
        currentSortBy = newSort;
        const sortSelect = document.getElementById('sort-by-select');
        if (sortSelect) {
            sortSelect.value = currentSortBy;
        }
        hasChanged = true;
    }
    
    if (currentR18Filter !== newR18) {
        currentR18Filter = newR18;
        const r18Select = document.getElementById('r18-filter-select');
        if (r18Select) {
            r18Select.value = currentR18Filter;
        }
        hasChanged = true;
    }
    
    // 如果有变化，重新加载数据
    if (hasChanged) {
        // 更新搜索UI
        updateSearchUI();
        // 重新加载数据
        loadPrompts(currentPage, currentSearchTerm, currentSortBy);
    }
}

/**
 * 更新标签筛选UI状态
 */
function updateTagFilterUI() {
    const tagBadges = document.querySelectorAll('.tag-badge');
    tagBadges.forEach(badge => {
        badge.classList.remove('active');
        if (currentTagFilter === '') {
            // 如果没有筛选，激活"全部"标签
            if (badge.textContent === '全部') {
                badge.classList.add('active');
            }
        } else if (badge.textContent === currentTagFilter) {
            badge.classList.add('active');
        }
    });
}

// 初始化函数 - 获取配置信息
async function initializeApp() {
    try {
        // 获取前端配置
        const response = await fetch(`${API_BASE_URL}/config`);
        if (!response.ok) {
            throw new Error('获取配置失败');
        }
        
        const config = await response.json();
        
        // 初始化配色方案
        initializeColorScheme();
        
        // 加载站公告
        loadSiteAnnouncement();
        
        // 不再需要加载标签列表
        // await loadTags(); 
        
        // 加载初始数据
        loadPrompts(currentPage);
        
        // 标记初始加载完成
        setTimeout(() => {
            isInitialLoad = false;
        }, 100);
    } catch (error) {
        console.error('初始化失败:', error);
        // 继续加载页面，即使配置获取失败
        loadPrompts(currentPage);
        
        // 标记初始加载完成
        setTimeout(() => {
            isInitialLoad = false;
        }, 100);
    }
}

// 不再需要加载所有标签用于筛选
/*
async function loadTags() {
    try {
        const response = await fetch(`${API_BASE_URL}/tags/`);
        if (!response.ok) {
            throw new Error('获取标签失败');
        }
        
        const tags = await response.json();
        
        // 渲染标签筛选列表
        renderTagFilters(tags);
    } catch (error) {
        console.error('加载标签失败:', error);
        // 标签加载失败不影响主界面
    }
}
*/

// 不再需要渲染标签筛选列表
/*
function renderTagFilters(tags) {
    // 保留"全部"标签
    const allTag = tagsFilterList.querySelector('.tag-badge[data-tag=""]');
    tagsFilterList.innerHTML = '';
    tagsFilterList.appendChild(allTag);
    
    // 添加所有标签
    tags.forEach(tag => {
        const tagElement = document.createElement('span');
        tagElement.className = 'tag-badge';
        tagElement.setAttribute('data-tag', tag.name);
        tagElement.textContent = tag.name;
        
        // 为标签添加点击事件
        tagElement.addEventListener('click', () => {
            // 更新UI状态
            document.querySelectorAll('.tag-badge').forEach(t => t.classList.remove('active'));
            tagElement.classList.add('active');
            
            // 设置当前筛选标签
            currentTagFilter = tag.name;
            // 清除搜索词，专注于标签筛选
            if (currentSearchTerm) {
                searchInput.value = "";
                currentSearchTerm = "";
                updateSearchUI();
            }
            currentPage = 1; // 重置到第一页
            
            // 重新加载数据
            loadPrompts(currentPage);
        });
        
        tagsFilterList.appendChild(tagElement);
    });
    
    // 为"全部"标签添加点击事件
    allTag.addEventListener('click', () => {
        // 更新UI状态
        document.querySelectorAll('.tag-badge').forEach(t => t.classList.remove('active'));
        allTag.classList.add('active');
        
        // 清除标签筛选
        currentTagFilter = "";
        currentPage = 1; // 重置到第一页
        
        // 重新加载数据
        loadPrompts(currentPage);
    });
}
*/

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
    // 初始化路由功能
    initRouting();
    
    // 页面初始化只在这里执行一次
    initializeApp();
    
    // 为所有按钮添加涟漪效果类
    const allButtons = document.querySelectorAll('button:not(.ripple-button)');
    allButtons.forEach(button => {
        button.classList.add('ripple-button');
        
        button.addEventListener('click', function(e) {
            // 只有没有disabled的按钮才添加涟漪效果
            if(!this.disabled) {
                createRippleEffect(this);
            }
        });
    });
    
    // 联系我们按钮事件
    if (contactUsBtn && contactUsPopup) {
        contactUsBtn.addEventListener('click', (event) => {
            event.stopPropagation(); // 防止点击事件冒泡到 document
            contactUsPopup.style.display = contactUsPopup.style.display === 'block' ? 'none' : 'block';
        });

        // 点击页面其他地方关闭弹窗
        document.addEventListener('click', (event) => {
            if (contactUsPopup.style.display === 'block' && !contactUsPopup.contains(event.target) && event.target !== contactUsBtn) {
                contactUsPopup.style.display = 'none';
            }
        });
    }
    
    // 特别确保详情页的点踩按钮有正确的类和事件监听器
    const dislikeBtn = document.getElementById('dislike-btn');
    if (dislikeBtn) {
        dislikeBtn.classList.add('ripple-button');
    }
    
    // 页面加载动画
    document.body.classList.add('page-loaded');
    
    // 添加初始动画类到主容器
    const container = document.querySelector('.container');
    if(container) {
        container.classList.add('animate-in');
    }
    
    // 页面加载完成，动画设置已就绪
    
    // 注册全局测试函数
    window.testBrokenHeartAnimation = testBrokenHeartAnimation;
});

// 页面切换功能
browseBtn.addEventListener('click', () => {
    setActivePage('browse');
});

uploadBtn.addEventListener('click', () => {
    setActivePage('upload');
});

function setActivePage(page) {
    // 如果点击的是当前页面，不执行切换动画
    if ((page === 'browse' && browseSection.classList.contains('active-section')) || 
        (page === 'upload' && uploadSection.classList.contains('active-section'))) {
        return;
    }
    
    // 移除当前活跃页面的类
    const activeSection = document.querySelector('.active-section');
    if (activeSection) {
        // 先让当前页面淡出
        activeSection.style.animation = 'fadeOut 0.3s ease forwards';
        
        // 在淡出动画结束后切换页面
        setTimeout(() => {
            if (page === 'browse') {
                browseBtn.classList.add('active');
                uploadBtn.classList.remove('active');
                browseSection.classList.add('active-section');
                uploadSection.classList.remove('active-section');
                // 确保重置动画
                browseSection.style.animation = '';
                // 加载提示列表
                loadPrompts(currentPage);
            } else {
                browseBtn.classList.remove('active');
                uploadBtn.classList.add('active');
                browseSection.classList.remove('active-section');
                uploadSection.classList.add('active-section');
                // 确保重置动画
                uploadSection.style.animation = '';
            }
            
            // 触发浏览器重绘以应用新的动画
            requestAnimationFrame(() => {
                const newActiveSection = document.querySelector('.active-section');
                if (page === 'browse') {
                    newActiveSection.style.animation = 'slideInFromLeft 0.4s ease forwards';
                } else {
                    newActiveSection.style.animation = 'slideInFromRight 0.4s ease forwards';
                }
            });
        }, 300);
    } else {
        // 如果没有活跃页面（初始加载）
        if (page === 'browse') {
            browseBtn.classList.add('active');
            uploadBtn.classList.remove('active');
            browseSection.classList.add('active-section');
            uploadSection.classList.remove('active-section');
            // 不在这里调用loadPrompts，因为initializeApp已经调用过了
            // 避免页面初始化时重复加载数据
        } else {
            browseBtn.classList.remove('active');
            uploadBtn.classList.add('active');
            browseSection.classList.remove('active-section');
            uploadSection.classList.add('active-section');
        }
    }
    
    // 添加按钮点击涟漪效果
    if (page === 'browse') {
        createRippleEffect(browseBtn);
    } else {
        createRippleEffect(uploadBtn);
    }
}

// 加载Prompt列表 - 使用优化的分页API
async function loadPrompts(page = 1, searchTerm = '', sortBy = 'upload_time_desc') {
    try {
        showLoading(true);
        
        // 使用新的分页端点，每页固定16个prompt
        let url = `${API_BASE_URL}/prompts/paginated?page=${page}`;
        
        // 添加搜索参数
        if (currentSearchTerm) {
            url += `&search=${encodeURIComponent(currentSearchTerm)}`;
        }
        
        // 添加标签筛选参数
        if (currentTagFilter) {
            url += `&tag=${encodeURIComponent(currentTagFilter)}`;
        }
        
        // 添加排序参数
        url += `&sort_by=${currentSortBy}`;
        
        // 添加R18筛选参数
        if (currentR18Filter === "non-r18") {
            url += "&is_r18=0"; // 仅显示非R18内容
        } else if (currentR18Filter === "r18-only") {
            url += "&is_r18=1"; // 仅显示R18内容
        } // 不添加参数表示显示所有内容
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error('网络请求失败');
        }
        
        const data = await response.json();
        
        // 渲染prompt列表
        renderPrompts(data.prompts);
        
        // 更新分页信息，使用新的响应格式
        updatePaginationWithData(data);
        
        // 显示分页统计信息
        updatePageStats(data);
        
        // 更新URL路由
        updateURL();
        
    } catch (error) {
        console.error('加载Prompt失败:', error);
        promptGrid.innerHTML = '<p class="error">加载失败，请稍后重试</p>';
    } finally {
        showLoading(false);
    }
}

// 渲染Prompt卡片
function renderPrompts(prompts) {
    promptGrid.innerHTML = '';
      if (prompts.length === 0) {
        // 显示没有结果的信息，并根据当前筛选条件提供不同的提示
        let noResultsMessage = '没有找到Prompt';
        let filterDescriptions = [];
        
        // 收集所有筛选条件的描述
        if (currentSearchTerm) {
            filterDescriptions.push(`包含 "${currentSearchTerm}"`);
        }
        
        if (currentTagFilter) {
            filterDescriptions.push(`标记为 "${currentTagFilter}"`);
        }
        
        if (currentR18Filter === "non-r18") {
            filterDescriptions.push("非R18内容");
        } else if (currentR18Filter === "r18-only") {
            filterDescriptions.push("R18内容");
        }
        
        // 根据筛选条件组合提示信息
        if (filterDescriptions.length > 0) {
            noResultsMessage = `没有找到${filterDescriptions.join('且')}的Prompt`;
        }
        
        promptGrid.innerHTML = `<p class="no-results">${noResultsMessage}</p>`;
        return;
    }
    
    // 使用文档片段进行批量DOM操作，提高性能
    const fragment = document.createDocumentFragment();
      // 添加交错加载动画
    prompts.forEach((prompt, index) => {
        const card = document.createElement('div');
        card.className = 'prompt-card';
        
        // 添加延迟加载动画类
        card.style.animationDelay = `${index * 50}ms`;
        
        // 截取描述，确保不会过长
        const description = prompt.description 
            ? (prompt.description.length > 100 
                ? prompt.description.substring(0, 100) + '...' 
                : prompt.description) 
            : '无描述';
        
        // 格式化日期
        const createdDate = new Date(prompt.created_at);
        const formattedDate = `${createdDate.getFullYear()}-${(createdDate.getMonth() + 1).toString().padStart(2, '0')}-${createdDate.getDate().toString().padStart(2, '0')}`;
        
        // 如果有搜索关键词，则高亮显示标题和描述
        const highlightedTitle = currentSearchTerm ? highlightText(prompt.title, currentSearchTerm) : prompt.title;
        const highlightedDescription = currentSearchTerm ? highlightText(description, currentSearchTerm) : description;
          // 生成标签HTML
        let tagsHtml = '';
        if (prompt.tags && prompt.tags.length > 0) {
            tagsHtml = '<div class="card-tags">';
            prompt.tags.forEach(tag => {
                // 如果有搜索关键词，则高亮显示标签
                const tagName = currentSearchTerm ? highlightText(tag.name, currentSearchTerm) : tag.name;
                tagsHtml += `<span class="tag-badge">${tagName}</span>`;
            });
            tagsHtml += '</div>';
        }
        
        // 生成作者信息HTML
        let authorHtml = '';
        if (prompt.owner) {
            const avatarUrl = prompt.owner.avatar_url || '/assets/images/default-avatar.jpg';
            const username = prompt.owner.username || '匿名用户';
            authorHtml = `
                <div class="card-author">
                    <img src="${avatarUrl}" alt="${username}" class="author-avatar" 
                         data-user-id="${prompt.owner.id}" data-username="${username}"
                         style="cursor: pointer;" 
                         onerror="this.src='/assets/images/default-avatar.jpg'">
                    <span class="author-name" 
                          data-user-id="${prompt.owner.id}" data-username="${username}"
                          style="cursor: pointer;">${username}</span>
                </div>
            `;
        }
        
        card.innerHTML = `
            <h3>${highlightedTitle} ${prompt.is_r18 ? '<span class="r18-badge">R18</span>' : ''}</h3>
            <p>${highlightedDescription}</p>
            ${tagsHtml}
            ${authorHtml}
            <div class="card-stats">
                <span>${formattedDate}</span>
                <span class="likes-count"><i class="fas fa-thumbs-up"></i> ${prompt.likes}</span>
                <span class="dislikes-count"><i class="fas fa-thumbs-down"></i> ${prompt.dislikes || 0}</span>
                <span class="views-count"><i class="fas fa-eye"></i> ${prompt.views || 0}</span>
            </div>
            <div class="card-actions">
                <button class="like-button ripple-button" data-id="${prompt.id}">
                    <i class="fas fa-thumbs-up"></i> 点赞
                </button>
                <button class="dislike-button ripple-button" data-id="${prompt.id}">
                    <i class="fas fa-thumbs-down"></i> 点踩
                </button>
                <button class="view-details ripple-button" data-id="${prompt.id}">查看详情</button>
            </div>
        `;
        
        fragment.appendChild(card);
        
        // 为查看详情按钮添加事件监听
        card.querySelector('.view-details').addEventListener('click', (e) => {
            e.preventDefault();
            createRippleEffect(e.currentTarget);
            openPromptDetails(prompt.id);
        });
        
        // 为点赞按钮添加事件监听
        card.querySelector('.like-button').addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            likePrompt(prompt.id, e.currentTarget);
        });

        // 为点踩按钮添加事件监听
        card.querySelector('.dislike-button').addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dislikePrompt(prompt.id, e.currentTarget);
        });
    });
      // 一次性将所有卡片添加到DOM中，减少重绘次数
    promptGrid.appendChild(fragment);
    
    // 如果没有显示任何提示卡片，显示提示信息
    if (promptGrid.children.length === 0) {
        const noResultsMessage = `当前的筛选条件下没有找到任何提示`;
        promptGrid.innerHTML = `<p class="no-results">${noResultsMessage}</p>`;
    }
}

// 分页控制 - 原有的简单版本
function updatePagination(page, isLastPage) {
    currentPageSpan.textContent = page;
    prevPageBtn.disabled = page === 1;
    nextPageBtn.disabled = isLastPage;
}

// 新的分页控制 - 处理详细的分页数据
function updatePaginationWithData(data) {
    // 计算总页数
    const totalPages = Math.ceil(data.total / data.per_page);
    
    // 更新页面显示为"x/y"格式（不包含"页"字，因为HTML中已有）
    currentPageSpan.textContent = `${data.page}/${totalPages}`;
    
    // 更新按钮状态
    prevPageBtn.disabled = data.page === 1;
    nextPageBtn.disabled = !data.has_more;
    
    // 更新当前页变量
    currentPage = data.page;
}

// 显示分页统计信息
function updatePageStats(data) {
    // 找到或创建统计信息显示区域
    let statsElement = document.getElementById('page-stats');
    if (!statsElement) {
        // 如果不存在，创建一个新的统计信息元素
        const pagination = document.querySelector('.pagination');
        if (pagination) {
            statsElement = document.createElement('div');
            statsElement.id = 'page-stats';
            statsElement.className = 'page-stats';
            pagination.appendChild(statsElement);
        }
    }
    
    if (statsElement) {
        const startItem = (data.page - 1) * data.per_page + 1;
        const endItem = Math.min(data.page * data.per_page, data.total);
        
        if (data.total === 0) {
            statsElement.innerHTML = `
                <small class="text-muted">
                    没有找到匹配的结果
                </small>
            `;
        } else {
            statsElement.innerHTML = `
                <small class="text-muted">
                    显示第 ${startItem}-${endItem} 项，共 ${data.total} 项结果
                </small>
            `;
        }
    }
}

prevPageBtn.addEventListener('click', () => {
    if (currentPage > 1) {
        currentPage--;
        loadPrompts(currentPage);
    }
});

nextPageBtn.addEventListener('click', () => {
    if (!nextPageBtn.disabled) {
        currentPage++;
        loadPrompts(currentPage);
    }
});

// 显示/隐藏加载状态
function showLoading(show) {
    loading.style.display = show ? 'block' : 'none';
}

// 打开Prompt详情模态窗口
async function openPromptDetails(id) {
    try {
        showLoading(true);
        
        const response = await fetch(`${API_BASE_URL}/prompts/${id}`);
        
        if (!response.ok) {
            throw new Error('获取Prompt详情失败');
        }
          const prompt = await response.json();
        currentPromptId = prompt.id;
        // 保存当前prompt标题用于聊天功能
        window.currentPromptTitle = prompt.title;
        
        // 填充模态窗口内容
        const titleContent = currentSearchTerm ? 
            highlightText(prompt.title, currentSearchTerm) : prompt.title;
        // 添加R18标记（如果适用）
        const r18Badge = prompt.is_r18 ? '<span class="r18-badge modal-r18">R18</span>' : '';
        document.getElementById('modal-title').innerHTML = `${titleContent} ${r18Badge}`;
        
        // 清除之前的作者信息（如果存在）
        const existingAuthorInfo = document.querySelector('.modal-author-info');
        if (existingAuthorInfo) {
            existingAuthorInfo.remove();
        }
        
        // 添加作者信息显示
        if (prompt.owner) {
            const authorInfoContainer = document.createElement('div');
            authorInfoContainer.className = 'modal-author-info';
            const avatarUrl = prompt.owner.avatar_url || '/assets/images/default-avatar.jpg';
            const username = prompt.owner.username || '匿名用户';
            authorInfoContainer.innerHTML = `
                <div class="author-info">
                    <img src="${avatarUrl}" alt="${username}" class="author-avatar" 
                         data-user-id="${prompt.owner.id}" data-username="${username}"
                         style="cursor: pointer;" 
                         onerror="this.src='/assets/images/default-avatar.jpg'">
                    <span class="author-name"
                          data-user-id="${prompt.owner.id}" data-username="${username}"
                          style="cursor: pointer;">作者: ${username}</span>
                </div>
            `;
            
            // 将作者信息插入到标题下方
            const modalStats = document.querySelector('.modal-stats');
            modalStats.parentNode.insertBefore(authorInfoContainer, modalStats);
        }
        
        const description = prompt.description || '无描述';
        document.getElementById('modal-description').innerHTML = currentSearchTerm ? 
            highlightText(description, currentSearchTerm) : description;
            
        // 内容不进行高亮处理，因为是代码
        document.getElementById('modal-content').textContent = prompt.content;
        
        document.getElementById('likes-count').textContent = prompt.likes;
        document.getElementById('dislikes-count').textContent = prompt.dislikes;
        document.getElementById('views-count').textContent = prompt.views || 0;
          // 渲染标签
        const tagsContainer = document.getElementById('modal-tags');
        tagsContainer.innerHTML = '';
        if (prompt.tags && prompt.tags.length > 0) {
            prompt.tags.forEach(tag => {
                const tagBadge = document.createElement('span');
                tagBadge.className = 'tag-badge';
                // 如果有搜索关键词，高亮标签
                tagBadge.innerHTML = currentSearchTerm ? 
                    highlightText(tag.name, currentSearchTerm) : tag.name;
                tagsContainer.appendChild(tagBadge);
            });
        } else {
            tagsContainer.innerHTML = '<span>无标签</span>';
        }
        
        // 格式化日期
        const createdDate = new Date(prompt.created_at);        document.getElementById('modal-date').textContent = `创建于 ${createdDate.toLocaleDateString()}`;        
        
        // 加载评论        
        loadComments(prompt.id);
        
        // 更新试用按钮状态
        const tryChatBtn = document.getElementById('try-chat-btn');
        if (tryChatBtn) {
            tryChatBtn.onclick = function() {
                // 检查用户是否登录 (isLoggedIn 函数在 github-login.js 中定义)
                if (typeof isLoggedIn === 'function' && !isLoggedIn()) {
                    showToast('请先登录后再试用聊天功能', 'info');
                    return;
                }

                // 检查openUnifiedChatWindow函数是否存在（在unified-chat.js中定义）
                if (typeof openUnifiedChatWindow === 'function') {
                    openUnifiedChatWindow(prompt.id, prompt.title);
                } else {
                    showToast('聊天功能加载失败，请刷新页面重试', 'error');
                }
            };
        }
        
        // 显示模态窗口，添加动画效果
        modal.classList.add('show'); // 先添加 show 类
        
        // 计算当前可视区域的中心点位置
        const scrollY = window.scrollY || window.pageYOffset;
        const viewportHeight = window.innerHeight;
        const viewportCenterY = scrollY + (viewportHeight / 2);
        
        // 给模态窗口内容添加进入动画
        const modalContent = modal.querySelector('.modal-content');
        if (modalContent) {
            // 设置模态框的位置为当前可视区域的中心
            modalContent.style.top = `${viewportCenterY}px`;
            modalContent.style.opacity = '0';
            modalContent.style.transform = 'translate(-50%, -50%) scale(0.9)';
            
            // 使用requestAnimationFrame确保CSS变化分两步执行
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    modalContent.style.opacity = '1';
                    modalContent.style.transform = 'translate(-50%, -50%) scale(1)';
                });
            });
        }
    } catch (error) {
        console.error('加载Prompt详情失败:', error);
        showToast('加载详情失败，请稍后重试', 'error');
    } finally {
        showLoading(false);
    }
}

// 关闭模态窗口
closeBtn.addEventListener('click', closeModal);

// 点击模态窗口外部关闭
window.addEventListener('click', (event) => {
    if (event.target === modal) {
        closeModal();
    }
});

// 当窗口滚动时，更新模态框位置
window.addEventListener('scroll', () => {
    if (modal.classList.contains('show')) {
        const modalContent = modal.querySelector('.modal-content');
        if (modalContent) {
            const scrollY = window.scrollY || window.pageYOffset;
            const viewportHeight = window.innerHeight;
            const viewportCenterY = scrollY + (viewportHeight / 2);
            modalContent.style.top = `${viewportCenterY}px`;
        }
    }
});

// 模态窗口关闭动画
function closeModal() {
    const modalContent = modal.querySelector('.modal-content');    
    // 添加模态窗口关闭动画
    if (modalContent) {
        modalContent.style.opacity = '0';
        modalContent.style.transform = 'translate(-50%, -50%) scale(0.9)';
    }
    // 整个模态淡出
    modal.classList.remove('show');
    
    // 动画完成后隐藏模态窗口
    setTimeout(() => {
        modal.style.display = 'none';
        currentPromptId = null;
          // 重置模态窗口样式以备下次使用
        if (modalContent) {
            modalContent.style.opacity = '';
            modalContent.style.transform = '';
        }
        
        // 清空评论区
        document.getElementById('comments-list').innerHTML = `
            <div id="comments-loading" style="display: none;">加载评论中...</div>
            <div id="no-comments-message" style="display: none;">暂无评论，快来发表第一条评论吧！</div>
        `;
        document.getElementById('comments-count').textContent = '(0)';
        commentsLoaded = false;
    }, 300);
}

// 复制Prompt内容
document.getElementById('copy-btn').addEventListener('click', (e) => {
    const copyBtn = document.getElementById('copy-btn');
    const content = document.getElementById('modal-content').textContent;
    
    // 创建涟漪效果
    createRippleEffect(copyBtn);
    
    // 使用更可靠的复制方法：创建一个临时textarea元素
    try {
        // 创建临时文本区域
        const textArea = document.createElement('textarea');
        textArea.value = content;
        textArea.style.position = 'fixed';  // 避免滚动到底部
        textArea.style.top = '0';
        textArea.style.left = '0';
        textArea.style.width = '2em';
        textArea.style.height = '2em';
        textArea.style.padding = '0';
        textArea.style.border = 'none';
        textArea.style.outline = 'none';
        textArea.style.boxShadow = 'none';
        textArea.style.background = 'transparent';
        textArea.style.opacity = '0';
        
        // 添加到文档并选择内容
        document.body.appendChild(textArea);
        textArea.select();
        textArea.setSelectionRange(0, textArea.value.length); // 兼容移动设备
        
        // 执行复制命令
        const successful = document.execCommand('copy');
        
        // 移除临时元素
        document.body.removeChild(textArea);
        
        if (successful) {
            // 添加成功视觉反馈
            copyBtn.innerHTML = '<i class="fas fa-check"></i> 已复制';
            copyBtn.classList.add('button-success');
            
            // 显示悬浮提示
            showToast('已复制到剪贴板', 'success');
            
            // 恢复按钮原始状态
            setTimeout(() => {
                copyBtn.innerHTML = '<i class="fas fa-copy"></i> 复制内容';
                copyBtn.classList.remove('button-success');
            }, 2000);
        } else {
            throw new Error('复制命令执行失败');
        }
    } catch (err) {
        console.error('复制失败:', err);
        
        // 尝试使用现代API作为备选
        navigator.clipboard.writeText(content).then(
            () => {
                // 添加成功视觉反馈
                copyBtn.innerHTML = '<i class="fas fa-check"></i> 已复制';
                copyBtn.classList.add('button-success');
                
                // 显示悬浮提示
                showToast('已复制到剪贴板', 'success');
                
                // 恢复按钮原始状态
                setTimeout(() => {
                    copyBtn.innerHTML = '<i class="fas fa-copy"></i> 复制内容';
                    copyBtn.classList.remove('button-success');
                }, 2000);
            },
            () => {
                showToast('复制失败，请手动复制', 'error');
                
                // 视觉反馈错误
                copyBtn.classList.add('button-error');
                setTimeout(() => {
                    copyBtn.classList.remove('button-error');
                }, 2000);
            }
        );
    }
});

// 全局爱心数量控制
let activeHeartCount = 0;
const MAX_HEARTS = 15; // 增加最大爱心数量，允许同时显示更多爱心
let isLikeInProgress = false;
let isDislikeInProgress = false; // 防止点踩重复点击
const likeDebounceTime = 500; // 500ms防抖，减少快速点击
const dislikeDebounceTime = 500; // 500ms防抖，减少快速点击
let lastLikeTimestamp = 0;
let lastDislikeTimestamp = 0; // 上次点踩时间戳
const MIN_CLICK_INTERVAL = 800; // 最小点击间隔，防止过快点击

// 点赞功能 - 增强版
async function likePrompt(id, buttonElement) {
    const now = Date.now();
    
    // 如果已有点赞请求正在处理中或距离上次点赞时间太短，则忽略此次点击
    if (isLikeInProgress || (now - lastLikeTimestamp < MIN_CLICK_INTERVAL)) {
        // 点赞操作被限制
        return;
    }
    
    // 更新最后点赞时间戳
    lastLikeTimestamp = now;
    
    // 设置标志防止重复点击
    isLikeInProgress = true;
    
    try {
        // 先播放动画，提升用户体验的即时性
        createHeartAnimation(buttonElement);
        
        // 给按钮添加涟漪效果
        createRippleEffect(buttonElement);
        
        const response = await fetch(`${API_BASE_URL}/prompts/${id}/like`, {
            method: 'PUT'
        });
          if (!response.ok) {
            throw new Error('点赞失败');
        }
        
        const result = await response.json();
        
        // 如果是在详情页中点赞，更新点赞数
        if (currentPromptId === id) {
            const likesCount = document.getElementById('likes-count');
            // 添加数字增加动画
            const oldValue = parseInt(likesCount.textContent);
            const newValue = result.likes;
            if (newValue > oldValue) {
                likesCount.classList.add('number-change');
                setTimeout(() => likesCount.classList.remove('number-change'), 500);
            }
            likesCount.textContent = newValue;
        } else {
            // 只更新当前卡片的点赞数，避免整页刷新
            const card = buttonElement.closest('.prompt-card');
            if (card) {
                const likeCountElement = card.querySelector('.card-stats span:nth-child(2)');
                if (likeCountElement) {
                    // 添加数字增加动画
                    likeCountElement.classList.add('number-change');
                    setTimeout(() => likeCountElement.classList.remove('number-change'), 500);
                    likeCountElement.innerHTML = `<i class="fas fa-thumbs-up"></i> ${result.likes}`;
                }
            }
        }
    } catch (error) {
        console.error('点赞失败:', error);
        // 使用更友好的错误提示，避免alert阻塞UI
        showToast('点赞失败，请稍后重试', 'error');
    } finally {
        // 点赞完成后重置标志，但加入短暂延迟，防止过快点击
        setTimeout(() => {
            isLikeInProgress = false;
        }, likeDebounceTime);
    }
}

// 显示通知消息
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.className = `toast toast-${type}`;
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: ${type === 'error' ? '#ff5252' : '#4caf50'};
        color: white;
        padding: 10px 20px;
        border-radius: 4px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.2);
        z-index: 10000;
        opacity: 0;
        transition: opacity 0.3s ease;
    `;
    
    document.body.appendChild(toast);
    
    // 强制重排，使过渡生效
    toast.offsetHeight;
    toast.style.opacity = '1';
    
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => {
            if (document.body.contains(toast)) {
                document.body.removeChild(toast);
            }
        }, 300);
    }, 2000);
}

// 创建爱心动画 - 增强版
function createHeartAnimation(sourceElement) {
    // 如果已达到最大爱心数量，不再创建新爱心，但仍提供视觉反馈
    if (activeHeartCount >= MAX_HEARTS) {
        // 添加按钮脉冲效果作为替代反馈
        sourceElement.classList.add('like-button-pulse');
        setTimeout(() => sourceElement.classList.remove('like-button-pulse'), 300);
        return;
    }
    
    try {
        // 添加按钮脉冲效果
        sourceElement.classList.add('like-button-pulse');
        setTimeout(() => sourceElement.classList.remove('like-button-pulse'), 300);
        
        // 获取按钮位置
        const rect = sourceElement.getBoundingClientRect();
        
        // 爱心起始位置（按钮中心）
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        
        // 创建多个爱心
        const heartCount = 3; // 一次创建3个爱心
        
        for (let i = 0; i < heartCount; i++) {
            // 避免超过最大爱心数量
            if (activeHeartCount >= MAX_HEARTS) break;
            
            // 创建爱心元素
            const heart = document.createElement('i');
            
            // 随机选择一种颜色和大小
            const colorClass = `heart-color-${Math.floor(Math.random() * 7) + 1}`;
            const sizeClass = `heart-size-${Math.floor(Math.random() * 5) + 1}`;
            const animClass = `heart-anim-${Math.floor(Math.random() * 3) + 1}`;
            heart.className = `fas fa-heart heart-animation ${colorClass} ${sizeClass} ${animClass}`;
            
            // 添加随机水平偏移量，每个爱心都有不同的起始位置，使动画更自然
            const randomOffset = Math.random() * 30 - 15; // -15px to +15px
            const randomDelay = i * 100; // 错开每个爱心的出现时间
            
            // 设置位置和延迟
            heart.style.left = `${centerX + randomOffset}px`;
            heart.style.top = `${centerY}px`;
            heart.style.animationDelay = `${randomDelay}ms`;
            
            // 增加爱心计数
            activeHeartCount++;
            
            // 添加到文档
            document.body.appendChild(heart);
            
            // 动画结束后移除爱心并减少计数，考虑延迟
            setTimeout(() => {
                if (document.body.contains(heart)) {
                    document.body.removeChild(heart);
                    activeHeartCount--;
                }
            }, 2000 + randomDelay); // 2秒动画时间 + 延迟时间
        }
    } catch (error) {
        console.error('创建爱心动画失败:', error);
        // 出错时也需要减少计数，确保不会卡住
        activeHeartCount = Math.max(0, activeHeartCount - 1);
    }
}

// 创建按钮涟漪效果
function createRippleEffect(button) {
    // 如果按钮已经禁用，不添加涟漪
    if (button.disabled) return;
    
    // 移除旧的涟漪元素
    const oldRipples = button.querySelectorAll('.ripple');
    oldRipples.forEach(ripple => {
        if (ripple.parentNode === button) {
            button.removeChild(ripple);
        }
    });
    
    // 创建新的涟漪元素
    const ripple = document.createElement('span');
    ripple.className = 'ripple ripple-primary';
    button.appendChild(ripple);
    
    // 设置涟漪的大小和位置
    const buttonRect = button.getBoundingClientRect();
    const size = Math.max(buttonRect.width, buttonRect.height);
    
    ripple.style.width = ripple.style.height = `${size}px`;
    ripple.style.left = `0px`;
    ripple.style.top = `0px`;
    
    // 涟漪完成后移除元素
    setTimeout(() => {
        if (ripple.parentNode === button) {
            button.removeChild(ripple);
        }
    }, 600);
}

// 不喜欢功能
document.getElementById('like-btn').addEventListener('click', async (e) => {
    if (currentPromptId) {
        await likePrompt(currentPromptId, e.currentTarget);
    }
});

document.getElementById('dislike-btn').addEventListener('click', async (e) => {
    if (currentPromptId) {
        // 详情页点踩按钮被点击
        // 调用通用的点踩函数，传入模态框中的按钮
        await dislikePrompt(currentPromptId, e.currentTarget);
    }
});


// 标签输入处理
const tagsInput = document.getElementById('prompt-tags');
const tagsContainer = document.getElementById('tags-container');
const tagsCount = document.getElementById('tags-count');
let currentTags = [];

// 处理标签输入
tagsInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && tagsInput.value.trim()) {
        e.preventDefault(); // 阻止表单提交
        const tagValue = tagsInput.value.trim();
        
        // 检查是否已达到5个标签
        if (currentTags.length >= 5) {
            alert('最多只能添加5个标签');
            return;
        }
        
        // 检查是否已存在相同标签
        if (currentTags.includes(tagValue)) {
            alert('标签已存在');
            return;
        }
        
        // 添加标签
        currentTags.push(tagValue);
        renderTags();
        tagsInput.value = '';
    }
});

// 渲染标签
function renderTags() {
    tagsContainer.innerHTML = '';
    currentTags.forEach((tag, index) => {
        const tagElement = document.createElement('div');
        tagElement.className = 'tag';
        tagElement.innerHTML = `
            <span>${tag}</span>
            <button data-index="${index}"><i class="fas fa-times"></i></button>
        `;
        tagsContainer.appendChild(tagElement);
        
        // 添加删除标签的事件监听
        tagElement.querySelector('button').addEventListener('click', function() {
            const index = parseInt(this.getAttribute('data-index'));
            currentTags.splice(index, 1);
            renderTags();
        });
    });
    
    // 更新标签计数
    tagsCount.textContent = currentTags.length;
}

// 上传Prompt表单处理
uploadForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    
    // 检查用户是否已登录
    const token = localStorage.getItem('promptmarket_token');
    if (!token) {
        alert('请先登录后再上传Prompt！');
        return;
    }
    
    const title = document.getElementById('prompt-title').value;
    const content = document.getElementById('prompt-content').value;
    const description = document.getElementById('prompt-description').value;
    // 修正标签获取方法，使用之前更新的 currentTags 数组
    const tags = currentTags;
    const isR18 = document.getElementById('prompt-r18').checked ? 1 : 0; // 获取R18选项状态
    
    try {
        const response = await fetch(`${API_BASE_URL}/prompts/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                title,
                content,
                description,
                tags,
                is_r18: isR18 // 添加R18字段
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            if (response.status === 401) {
                alert('登录已过期，请重新登录！');
                // 清除过期token
                localStorage.removeItem('promptmarket_token');
                // 更新登录状态
                updateLoginState(false);
                return;
            }
            throw new Error(errorData.detail || '上传失败');
        }
        
        alert('Prompt上传成功，等待审核！');
        uploadForm.reset(); // 重置表单
        // 重置标签数据
        currentTags = [];
        document.getElementById('tags-container').innerHTML = '';
        document.getElementById('tags-count').textContent = '0';
        // 重置R18选项
        document.getElementById('prompt-r18').checked = false;
        setActivePage('browse'); // 切换回浏览页面
    } catch (error) {
        console.error('上传失败:', error);
        alert(`上传失败: ${error.message}`);
    }
});

// 搜索功能
// searchBtn.addEventListener('click', performSearch); // 改为实时搜索，不再需要点击按钮

// 输入框内容变化时触发搜索（实时搜索）
searchInput.addEventListener('input', () => {
    // 添加防抖，避免过于频繁的API请求
    debounce(performSearch, 300)(); // 300毫秒防抖
});

// 输入框回车触发搜索 (保留此功能，以便用户习惯)
searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        performSearch();
    }
});

// 执行搜索
function performSearch() {
    const searchTerm = searchInput.value.trim();
    
    // 如果搜索词与当前搜索词相同且为空，不做任何操作
    if (searchTerm === currentSearchTerm && searchTerm === '') {
        return;
    }
    
    // 更新当前搜索词
    currentSearchTerm = searchTerm;
    
    // 重置到第一页
    currentPage = 1;
    
    // 重新加载数据
    loadPrompts(currentPage);
    
    // 添加搜索动画效果
    const searchBar = searchInput.parentElement;
    searchBar.classList.add('search-active');
    setTimeout(() => {
        searchBar.classList.remove('search-active');
    }, 500);
    
    // 更新搜索UI
    updateSearchUI();
}

// 清除搜索按钮
clearSearchBtn.addEventListener('click', () => {
    // 清除搜索框内容
    searchInput.value = "";
    
    // 清除当前搜索词
    currentSearchTerm = "";
    
    // 更新UI
    updateSearchUI();
    
    // 重新加载数据
    currentPage = 1;
    loadPrompts(currentPage);
});


r18FilterSelect.addEventListener('change', (e) => {
    currentR18Filter = e.target.value;
    currentPage = 1; // R18筛选更改时重置到第一页
    loadPrompts(currentPage, currentSearchTerm, currentSortBy);
});

// 更新搜索UI
function updateSearchUI() {
    // 如果有搜索词，为搜索栏添加活跃状态
    if (currentSearchTerm) {
        searchInput.parentElement.classList.add('has-search-term');
        searchInput.setAttribute('title', `搜索: ${currentSearchTerm}`);
        clearSearchBtn.style.display = 'block';
    } else {
        searchInput.parentElement.classList.remove('has-search-term');
        searchInput.removeAttribute('title');
        clearSearchBtn.style.display = 'none';
    }
}

// 排序选择事件监听
sortBySelect.addEventListener('change', (event) => {
    currentSortBy = event.target.value;
    currentPage = 1; // 排序更改时重置到第一页
    loadPrompts(currentPage, currentSearchTerm, currentSortBy);
});

// 高亮文本中的关键词
function highlightText(text, keyword) {
    if (!keyword || !text) return text;
    
    // 转义正则表达式特殊字符
    const escapeRegExp = (string) => {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    };
    
    // 构建正则表达式，不区分大小写
    const regex = new RegExp(`(${escapeRegExp(keyword)})`, 'gi');
    
    // 替换文本，添加高亮标签
    return text.replace(regex, '<span class="highlight">$1</span>');
}

// 页面加载完成后执行 - 这里不再重复初始化应用，避免双重加载
document.addEventListener('DOMContentLoaded', () => {
    // 不再需要重复调用initializeApp()，因为在上面的DOMContentLoaded事件里已经调用过了
    
    // 默认显示浏览页面
    setActivePage('browse');
    
    // 为R18筛选选择器添加事件监听
    if (r18FilterSelect) {
        r18FilterSelect.addEventListener('change', (event) => {
            currentR18Filter = event.target.value;
            currentPage = 1; // 筛选更改时重置到第一页
            loadPrompts(currentPage);
        });
    }
});

// 为评论提交按钮添加事件监听
document.addEventListener('DOMContentLoaded', function() {
    // 初始化应用
    initializeApp();
    
    // 监听登录状态变化，更新评论表单状态
    updateCommentFormState();
    
    // 针对评论提交按钮添加事件监听器
    const submitCommentBtn = document.getElementById('submit-comment-btn');
    const commentInput = document.getElementById('comment-input');
    
    if (submitCommentBtn && commentInput) {
        submitCommentBtn.addEventListener('click', () => {
            const content = commentInput.value.trim();
            if (content && currentPromptId) {
                submitComment(currentPromptId, content);
            } else if (!content) {
                showToast('请输入评论内容', 'warning');
            }
        });
        
        // 在评论输入框中按回车键提交评论
        commentInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault(); // 阻止默认行为（换行）
                if (!submitCommentBtn.disabled) {
                    submitCommentBtn.click(); // 模拟点击提交按钮
                }
            }
        });
    }
});

// 为标签添加点击事件，点击卡片上的标签进行筛选
document.addEventListener('click', function(e) {
    // 通过事件委托捕获标签点击
    if (e.target.classList.contains('tag-badge') || e.target.parentElement.classList.contains('tag-badge')) {
        e.preventDefault();
        e.stopPropagation();
        
        // 获取标签文本内容（移除可能存在的高亮HTML）
        const tagElement = e.target.classList.contains('tag-badge') ? e.target : e.target.parentElement;
        const tagText = tagElement.textContent.trim();
        
        // 设置搜索框为该标签内容
        searchInput.value = tagText;
        performSearch();
    }
});

// 点踩功能
async function dislikePrompt(id, button) {
    const now = Date.now();
    
    // 如果已有点踩请求正在处理中或距离上次点踩时间太短，则忽略此次点击
    if (isDislikeInProgress || (now - lastDislikeTimestamp < MIN_CLICK_INTERVAL)) {
        // 点踩操作被限制
        return;
    }
    
    // 更新最后点踩时间戳
    lastDislikeTimestamp = now;
    
    // 设置标志防止重复点击
    isDislikeInProgress = true;
    
    try {
        // 先显示动画效果，提升用户体验的即时性
        createBrokenHeartAnimation(button); // 调用新的破碎爱心动画
        
        // 添加涟漪效果
        createRippleEffect(button);

        const response = await fetch(`${API_BASE_URL}/prompts/${id}/dislike`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '点踩失败');
        }

        const result = await response.json();

        // 更新卡片上的点踩数
        const card = button.closest('.prompt-card');
        if (card) {
            const dislikesCountElement = card.querySelector('.dislikes-count');
            if (dislikesCountElement) {
                // 添加数字变化动画
                dislikesCountElement.classList.add('number-change');
                setTimeout(() => dislikesCountElement.classList.remove('number-change'), 500);
                dislikesCountElement.innerHTML = `<i class="fas fa-thumbs-down"></i> ${result.dislikes}`;
            }
        }

        // 更新模态框中的点踩数 (如果模态框打开且是当前prompt)
        if (modal.classList.contains('show') && currentPromptId === id) {
            const modalDislikesCount = document.getElementById('dislikes-count');
            modalDislikesCount.classList.add('number-change');
            setTimeout(() => modalDislikesCount.classList.remove('number-change'), 500);
            modalDislikesCount.textContent = result.dislikes;
        }

    } catch (error) {
        console.error('点踩失败:', error);
        showToast('点踩失败，请稍后重试', 'error');
    } finally {
        // 点踩完成后重置标志，但加入短暂延迟，防止过快点击
        setTimeout(() => {
            isDislikeInProgress = false;
        }, dislikeDebounceTime);
    }
}

// 创建爱心破碎动画 - 裂成两半版本
function createBrokenHeartAnimation(sourceElement) {
    try {
        // 创建爱心破碎动画
        
        // 添加按钮脉冲效果 (可选)
        sourceElement.classList.add('like-button-pulse');
        setTimeout(() => sourceElement.classList.remove('like-button-pulse'), 300);

        const rect = sourceElement.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        
        // 计算动画中心点坐标

        // 创建左半边心
        const leftHalf = document.createElement('i');
        leftHalf.className = 'fas fa-heart heart-half heart-left-half'; // 使用完整的实心爱心图标
        leftHalf.style.position = 'fixed'; // 确保使用fixed定位，避免滚动影响
        leftHalf.style.zIndex = '10000'; // 确保在模态框上方显示
        document.body.appendChild(leftHalf);
        
        // 创建右半边心
        const rightHalf = document.createElement('i');
        rightHalf.className = 'fas fa-heart heart-half heart-right-half'; // 使用完整的实心爱心图标
        rightHalf.style.position = 'fixed'; // 确保使用fixed定位，避免滚动影响
        rightHalf.style.zIndex = '10000'; // 确保在模态框上方显示
        document.body.appendChild(rightHalf);
          // 设置初始尺寸，确保两个部分大小相同
        const heartSize = '24px';
        leftHalf.style.fontSize = heartSize;
        rightHalf.style.fontSize = heartSize;
        
        // 确保元素在创建时有正确的宽高
        leftHalf.style.width = '24px';
        leftHalf.style.height = '24px';
        rightHalf.style.width = '24px';
        rightHalf.style.height = '24px';
        
        // 设置明确的显示和文本对齐
        leftHalf.style.display = 'inline-block';
        rightHalf.style.display = 'inline-block';
        leftHalf.style.textAlign = 'center';
        rightHalf.style.textAlign = 'center';
        
        // 设置起始位置 - 元素已在DOM中，现在可以安全获取尺寸
        leftHalf.style.left = `${centerX - (leftHalf.offsetWidth / 2)}px`; // 微调位置，使其看起来像从中心裂开
        leftHalf.style.top = `${centerY - (leftHalf.offsetHeight / 2)}px`;
        
        rightHalf.style.left = `${centerX - (rightHalf.offsetWidth / 2)}px`;
        rightHalf.style.top = `${centerY - (rightHalf.offsetHeight / 2)}px`;

        // 动画结束后移除元素
        const animationDuration = 1200; // 对应CSS中的动画时长 1.2s
        setTimeout(() => {
            if (document.body.contains(leftHalf)) {
                document.body.removeChild(leftHalf);
            }
            if (document.body.contains(rightHalf)) {
                document.body.removeChild(rightHalf);
            }
        }, animationDuration);

    } catch (error) {
        console.error('创建裂开爱心动画失败:', error);
    }
}

// 防抖函数
let debounceTimer;
function debounce(func, delay) {
    return function() {
        const context = this;
        const args = arguments;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => func.apply(context, args), delay);
    }
}

// 测试函数 - 可以从控制台直接调用测试爱心破碎动画
function testBrokenHeartAnimation() {
    // 测试爱心破碎动画
    const dislikeBtn = document.getElementById('dislike-btn');
    if (dislikeBtn) {
        // 找到点踩按钮，测试动画
        createBrokenHeartAnimation(dislikeBtn);
        return '测试发送成功';
    } else {
        console.error('未找到点踩按钮');
        return '测试失败：未找到点踩按钮';
    }
}

// 配色方案功能
const colorSchemeSelect = document.getElementById('color-scheme-select');

// 初始化配色方案
function initializeColorScheme() {
    // 检测浏览器是否支持CSS变量
    if (!isCustomPropertySupported()) {
        // 如果不支持CSS变量，隐藏配色选择器
        const schemeSelector = document.querySelector('.color-scheme-selector');
        if (schemeSelector) {
            schemeSelector.style.display = 'none';
        }
        console.warn('该浏览器不支持CSS变量，配色方案功能不可用');
        return;
    }
    
    // 从本地存储读取用户之前选择的配色方案
    const savedScheme = localStorage.getItem('colorScheme');
    if (savedScheme) {
        applyColorScheme(savedScheme);
        colorSchemeSelect.value = savedScheme;
    }
    
    // 添加过渡效果，使颜色变换更平滑
    document.documentElement.style.transition = 'background-color 0.5s ease';
    document.body.style.transition = 'background-color 0.5s ease, color 0.5s ease';
}

// 检查浏览器是否支持CSS变量
function isCustomPropertySupported() {
    return (window.CSS && 
            window.CSS.supports && 
            window.CSS.supports('--a', '0')) || 
           (typeof document.body.style.setProperty === 'function');
}

// 应用配色方案
function applyColorScheme(scheme) {
    // 移除所有颜色方案类
    document.body.classList.remove(
        'color-scheme-sky', 
        'color-scheme-mint', 
        'color-scheme-lavender', 
        'color-scheme-sunset', 
        'color-scheme-dark'
    );
    
    // 如果不是默认方案，添加对应的类
    if (scheme !== 'default') {
        document.body.classList.add(`color-scheme-${scheme}`);
    }
    
    // 保存用户选择到本地存储
    localStorage.setItem('colorScheme', scheme);
    
    // 显示切换提示
    showThemeChangeNotification(scheme);
}

// 显示主题切换提示
function showThemeChangeNotification(scheme) {
    // 创建提示元素
    const notification = document.createElement('div');
    
    // 根据选择的主题设置提示文本
    let themeName = '';
    switch(scheme) {
        case 'default': themeName = '樱花粉'; break;
        case 'sky': themeName = '天空蓝'; break;
        case 'mint': themeName = '薄荷绿'; break;
        case 'lavender': themeName = '紫罗兰'; break;
        case 'sunset': themeName = '黄昏橙'; break;
        case 'dark': themeName = '深色模式'; break;
    }
    
    // 设置提示内容和样式
    notification.textContent = `已切换到 ${themeName} 主题`;
    notification.style.position = 'fixed';
    notification.style.bottom = '20px';
    notification.style.left = '50%';
    notification.style.transform = 'translateX(-50%)';
    notification.style.padding = '10px 20px';
    notification.style.backgroundColor = 'var(--primary-button-bg, #FFB6C1)';
    notification.style.color = 'white';
    notification.style.borderRadius = '4px';
    notification.style.zIndex = '9999';
    notification.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.2)';
    notification.style.opacity = '0';
    notification.style.transition = 'opacity 0.3s ease';
    
    // 添加到页面
    document.body.appendChild(notification);
    
    // 显示提示
    setTimeout(() => {
        notification.style.opacity = '1';
    }, 100);
    
    // 3秒后自动消失
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => {
            if (document.body.contains(notification)) {
                document.body.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

// 监听配色方案选择变化
colorSchemeSelect.addEventListener('change', (e) => {
    applyColorScheme(e.target.value);
});

// 页面加载后初始化配色方案
document.addEventListener('DOMContentLoaded', initializeColorScheme);

// 站内信功能
let unreadMessageCount = 0;
let messageCheckInterval = null;

/**
 * 初始化站内信功能
 */
function initMessagesFeature() {
    const messagesBtn = document.getElementById('messages-btn');
    if (messagesBtn) {
        messagesBtn.addEventListener('click', function(e) {
            e.preventDefault();
            // 跳转到私信页面
            window.location.href = 'private-messages.html';
        });
    }
    
    // 启动未读消息检查
    startUnreadMessageCheck();
}

/**
 * 启动未读消息检查
 */
function startUnreadMessageCheck() {
    // 如果用户已登录，开始定期检查未读消息
    const token = localStorage.getItem('promptmarket_token');
    if (token) {
        // 立即检查一次
        checkUnreadMessages();
        
        // 每30秒检查一次未读消息
        messageCheckInterval = setInterval(checkUnreadMessages, 30000);
    }
}

/**
 * 停止未读消息检查
 */
function stopUnreadMessageCheck() {
    if (messageCheckInterval) {
        clearInterval(messageCheckInterval);
        messageCheckInterval = null;
    }
    // 重置未读消息计数
    updateUnreadMessageBadge(0);
}

/**
 * 检查未读消息计数
 */
async function checkUnreadMessages() {
    const token = localStorage.getItem('promptmarket_token');
    if (!token) {
        stopUnreadMessageCheck();
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/messages/unread-count`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            updateUnreadMessageBadge(data.unread_count || 0);
        } else if (response.status === 401) {
            // Token过期，停止检查
            stopUnreadMessageCheck();
        }
    } catch (error) {
        console.error('检查未读消息失败:', error);
    }
}

/**
 * 更新未读消息徽章
 */
function updateUnreadMessageBadge(count) {
    unreadMessageCount = count;
    const badge = document.getElementById('unread-messages-badge');
    
    if (badge) {
        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : count.toString();
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    }
}

// 在用户登录状态改变时，启动或停止消息检查
document.addEventListener('DOMContentLoaded', function() {
    // 初始化站内信功能
    initMessagesFeature();
    
    // 监听存储变化，当用户登录状态改变时更新消息检查
    window.addEventListener('storage', function(e) {
        if (e.key === 'promptmarket_token') {
            if (e.newValue) {
                startUnreadMessageCheck();
            } else {
                stopUnreadMessageCheck();
            }
        }
    });
});

// =========================
// 站公告相关功能
// =========================

/**
 * 加载站公告
 */
async function loadSiteAnnouncement() {
    try {
        const response = await fetch(`${API_BASE_URL}/announcement`);
        if (!response.ok) {
            // 如果没有公告或获取失败，不显示错误
            hideSiteAnnouncement();
            return;
        }
        
        const announcement = await response.json();
        if (announcement && announcement.title && announcement.content) {
            displaySiteAnnouncement(announcement);
        } else {
            hideSiteAnnouncement();
        }
    } catch (error) {
        console.log('加载站公告失败:', error);
        hideSiteAnnouncement();
    }
}

/**
 * 显示站公告
 */
function displaySiteAnnouncement(announcement) {
    const announcementElement = document.getElementById('site-announcement');
    const titleElement = document.getElementById('announcement-title');
    const textElement = document.getElementById('announcement-text');
    const dateElement = document.getElementById('announcement-date');
    
    if (!announcementElement) return;
    
    // 填充公告内容
    titleElement.textContent = announcement.title;
    textElement.textContent = announcement.content;
    
    // 格式化创建时间
    const createdDate = new Date(announcement.created_at);
    dateElement.textContent = `发布时间: ${createdDate.toLocaleString('zh-CN')}`;
    
    // 显示公告
    announcementElement.style.display = 'block';
    
    // 绑定关闭按钮事件
    const closeBtn = document.getElementById('close-announcement');
    if (closeBtn) {
        closeBtn.onclick = function() {
            hideSiteAnnouncement();
            // 将关闭状态保存到本地存储，避免在本次会话中重复显示
            sessionStorage.setItem('announcement_closed_' + announcement.id, 'true');
        };
    }
    
    // 检查是否在本次会话中已经关闭过
    const isClosed = sessionStorage.getItem('announcement_closed_' + announcement.id);
    if (isClosed === 'true') {
        hideSiteAnnouncement();
    }
}

/**
 * 隐藏站公告
 */
function hideSiteAnnouncement() {
    const announcementElement = document.getElementById('site-announcement');
    if (announcementElement) {
        announcementElement.style.display = 'none';
    }
}
