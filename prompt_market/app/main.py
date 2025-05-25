from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from .crud import router as crud_router
from .admin import admin_router
from .auth import auth_router
from .chat import chat_router  # 导入聊天路由
from .user_profile import user_profile_router  # 导入用户主页路由
from .notifications import notifications_router  # 导入站内信路由
import pathlib # 新增导入
from fastapi import Request, Response
from .config import GITHUB_CLIENT_ID, GITHUB_REDIRECT_URI # 导入GitHub OAuth配置

# --- 新增代码：定义 frontend 目录的绝对路径 ---
# main.py 所在的目录 (app/)
APP_DIR = pathlib.Path(__file__).resolve().parent
# 项目根目录 (prompt_market/)
PROJECT_ROOT = APP_DIR.parent
# frontend 目录的绝对路径
FRONTEND_DIR = PROJECT_ROOT / "frontend"
# --- 结束新增代码 ---

app = FastAPI(
    title="Prompt Market API",
    description="API for managing and sharing LLM System Prompts",
    version="0.1.0",
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://www.jasongjz.top:8000", # 新增：允许来自端口 8000 的请求
        "http://localhost:8000",       # 新增：允许本地端口 8000
        "http://127.0.0.1:8000"      # 新增：允许本地端口 8000
    ], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crud_router, prefix="/api/v1", tags=["prompts"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])  # 添加聊天路由
app.include_router(user_profile_router, prefix="/api/v1", tags=["user-profile"])  # 添加用户主页路由
app.include_router(notifications_router, prefix="/api/v1", tags=["notifications"])  # 添加站内信路由

# Mount static file directory to /app
# 修改 directory 参数以使用绝对路径
app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="app_frontend") # 显式添加 html=True
# 修改 directory 参数以使用绝对路径
app.mount("/docs", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend_on_docs") # 保留之前的 /docs 挂载
# 挂载管理页面
app.mount("/admin", StaticFiles(directory=APP_DIR / "static" / "admin", html=True), name="admin_frontend")

from fastapi.responses import RedirectResponse

@app.get("/")
async def root():
    """根路径重定向到前端页面"""
    return RedirectResponse(url="/app/index.html")

@app.get("/admin-login")
async def admin_login():
    """管理员登录页面重定向"""
    return RedirectResponse(url="/admin/login.html")

# 新增：获取前端配置API
@app.get("/api/v1/config")
async def get_frontend_config():
    """获取前端需要的配置数据"""
    return {
        "github_login": {
            "enabled": bool(GITHUB_CLIENT_ID),  # 如果配置了Client ID，则启用GitHub登录
            "login_url": "/api/v1/auth/github/login"  # GitHub登录URL
        }
    }


