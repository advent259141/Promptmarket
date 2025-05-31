from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.services.crud import router as crud_router
from app.api.admin import admin_router
from app.api.auth import auth_router
from app.api.unified_chat import unified_chat_router  # 导入统一聊天路由
from app.api.user_profile import user_profile_router  # 导入用户主页路由
from app.api.private_messages import private_message_router  # 导入私信路由
from app.api.notifications import notification_router  # 导入通知路由
import pathlib # 新增导入
from app.core.config import GITHUB_CLIENT_ID, GITHUB_REDIRECT_URI # 导入GitHub OAuth配置

# --- 新增代码：定义 frontend 目录的绝对路径 ---
# main.py 所在的目录 (backend/)
APP_DIR = pathlib.Path(__file__).resolve().parent
# 项目根目录 (prompt_market/)
PROJECT_ROOT = APP_DIR.parent
# frontend 目录的绝对路径
FRONTEND_DIR = PROJECT_ROOT / "frontend"
# backend/app 目录的绝对路径
BACKEND_APP_DIR = APP_DIR / "app"
# --- 结束新增代码 ---

app = FastAPI(
    title="Prompt Market API",
    description="API for managing and sharing LLM System Prompts",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://www.jasongjz.top",      # 反向代理后的域名（不带端口）
        "https://www.jasongjz.top",     # 支持HTTPS
        "http://www.jasongjz.top:8000", # 保留：直接访问8000端口
        "http://localhost:8000",        # 本地开发环境
        "http://127.0.0.1:8000",        # 本地开发环境
        # 新增域名
        "http://prompt.wenturc.com",    # wenturc.com 域名
        "https://prompt.wenturc.com",   # wenturc.com 域名 HTTPS
        "http://prompts.wenturc.com",   # wenturc.com 域名复数
        "https://prompts.wenturc.com",  # wenturc.com 域名复数 HTTPS
        "http://promptss.wenturc.com",  # wenturc.com 域名三个s
        "https://promptss.wenturc.com", # wenturc.com 域名三个s HTTPS
        "http://prompt.521.wiki",       # 521.wiki 域名
        "https://prompt.521.wiki"       # 521.wiki 域名 HTTPS
    ], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crud_router, prefix="/api/v1", tags=["prompts"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(unified_chat_router, prefix="/api/v1", tags=["unified-chat"])  # 添加统一聊天路由
app.include_router(user_profile_router, prefix="/api/v1", tags=["user-profile"])  # 添加用户主页路由
app.include_router(private_message_router, prefix="/api/v1/messages", tags=["private-messages"])  # 添加私信路由
app.include_router(notification_router, prefix="/api/v1/messages", tags=["notifications"])  # 添加通知路由

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

# 挂载管理页面
app.mount("/admin", StaticFiles(directory=BACKEND_APP_DIR / "static" / "admin", html=True), name="admin_frontend")

# 挂载app/static目录为/app静态文件路径
app.mount("/app", StaticFiles(directory=BACKEND_APP_DIR / "static"), name="app_static")

# 挂载前端静态资源
app.mount("/src", StaticFiles(directory=FRONTEND_DIR / "src"), name="frontend_src")
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="frontend_assets")

# 挂载前端首页到根路径 - 这个必须放在最后
app.mount("/", StaticFiles(directory=FRONTEND_DIR / "src" / "pages", html=True), name="frontend_root")


