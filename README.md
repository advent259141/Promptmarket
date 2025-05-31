# Prompt Market 项目文档

## 🚀 快速启动

### 1. 环境准备
```bash
# 安装 Python 依赖
cd backend
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置数据库连接等信息
```

### 2. 数据库设置
项目使用 MySQL 数据库，详细配置请参考 [MySQL 设置指南](./MYSQL_SETUP.md)

### 3. 启动服务
```bash
# 在 backend 目录下启动后端服务
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 或使用 Python 直接运行
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

启动成功后，服务将在 `http://localhost:8000` 运行。

## 📚 API 文档

### 自动生成的 API 文档
启动服务后，可以通过以下地址访问交互式 API 文档：

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### 主要 API 端点
- `/api/v1/prompts` - Prompt CRUD 操作
- `/api/v1/admin` - 管理员相关接口
- `/api/v1/auth` - 用户认证（包括 GitHub OAuth）
- `/api/v1/messages` - 私信和通知系统
- `/api/v1/user-profile` - 用户资料管理
- `/api/v1/config` - 前端配置获取

## 🌐 域名配置

### 修改允许的域名
在 `backend/main.py` 文件中找到 CORS 中间件配置，修改 `allow_origins` 列表：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",        # 本地开发环境
        "http://127.0.0.1:8000",        # 本地开发环境
        "http://your-domain.com",       # 添加您的域名
        "https://your-domain.com",      # HTTPS 版本
        # 添加更多域名...
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 支持的域名类型
- HTTP 和 HTTPS 协议
- 带端口号和不带端口号的域名
- 子域名配置

## 👨‍💼 管理员功能

### 访问管理页面
管理页面可以通过以下方式访问：

1. **直接访问**: `http://localhost:8000/admin`
2. **登录重定向**: `http://localhost:8000/admin-login`

### 管理员登录
管理页面使用独立的认证系统，需要管理员账号密码登录。

### 创建管理员账号
使用提供的脚本创建管理员账号：

```bash
# 在 backend 目录下运行
cd backend
python scripts/create_admin.py

# 按提示输入管理员信息
# 用户名: admin
# 密码: [设置安全密码]
# 邮箱: admin@example.com
```

### 管理员功能
- Prompt 内容管理（审核、编辑、删除）
- 用户管理
- 系统设置
- 数据统计

## 🔐 GitHub OAuth 配置

### 启用 GitHub 登录
1. 在 GitHub 创建 OAuth App
2. 在 `.env` 文件中配置：
```env
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_REDIRECT_URI=http://localhost:8000/api/v1/auth/github/callback
```

### GitHub 登录流程
- 前端通过 `/api/v1/config` 检查是否启用 GitHub 登录
- 用户点击 GitHub 登录按钮
- 重定向到 `/api/v1/auth/github/login`
- 完成 OAuth 流程后返回应用

## 📁 项目结构

```
prompt_market/
├── backend/                 # 后端服务
│   ├── main.py             # 主应用入口
│   ├── app/                # 应用代码
│   │   ├── api/            # API 路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务逻辑
│   │   └── static/         # 静态文件
│   └── scripts/            # 工具脚本
├── frontend/               # 前端资源
│   ├── src/               # 源代码
│   └── assets/            # 静态资源
└── docs/                  # 项目文档
```

## 🐳 Docker 部署

使用 Docker Compose 快速部署：

```bash
# 启动服务（包括 MySQL 数据库）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 停止服务
docker-compose down
```

## 🔧 常见问题

### 1. 数据库连接失败
- 检查 MySQL 服务是否启动
- 验证 `.env` 文件中的数据库配置
- 确保数据库已创建

### 2. 前端资源加载失败
- 确认 `frontend` 目录结构正确
- 检查静态文件挂载配置
- 验证文件路径是否正确

### 3. GitHub OAuth 不工作
- 检查 GitHub OAuth App 配置
- 验证 `.env` 文件中的 GitHub 配置
- 确认回调 URL 设置正确

### 4. 跨域请求被阻止
- 在 `main.py` 中添加您的域名到 `allow_origins`
- 确保包含 HTTP 和 HTTPS 版本
- 重启服务使配置生效

## 📞 技术支持

如有问题，请检查：
1. 服务器日志输出
2. 浏览器控制台错误
3. API 文档中的接口说明
4. 数据库连接状态

---

**快速参考**:
- 🌍 前端页面: `http://localhost:8000`
- 📖 API 文档: `http://localhost:8000/docs`
- 🛠️ 管理页面: `http://localhost:8000/admin`
- 📊 ReDoc: `http://localhost:8000/redoc`
