from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel

from ..models import models
from ..schemas import schemas
from ..core.database import get_db
from ..core.github_auth import GitHubOAuth, get_or_create_github_user
from ..core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

# 创建路由
auth_router = APIRouter()

# 密码上下文，用于密码哈希和验证
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 密码bearer令牌
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token", auto_error=False)

# Pydantic模型
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    is_admin: Optional[int] = 0

class UserInDB(BaseModel):
    id: int
    username: str
    is_admin: int

# 辅助函数
def verify_password(plain_password, hashed_password):
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """获取密码哈希值"""
    return pwd_context.hash(password)

async def get_user(username: str, db: AsyncSession):
    """根据用户名获取用户"""
    query = select(models.User).filter(models.User.username == username)
    result = await db.execute(query)
    user = result.scalars().first()
    if user:
        return user
    return None

async def authenticate_user(username: str, password: str, db: AsyncSession):
    """验证用户"""
    user = await get_user(username, db)
    if not user:
        return False
    if not user.hashed_password:  # OAuth用户没有密码
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    """获取当前用户"""
    if not token:
        return None
        
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = await get_user(username=token_data.username, db=db)
    if user is None:
        raise credentials_exception
    return user

async def get_current_admin(current_user: models.User = Depends(get_current_user)):
    """获取当前管理员"""
    if current_user.is_admin != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Insufficient permissions. Admin access required."
        )
    return current_user

# 路由
@auth_router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """登录获取令牌"""
    user = await authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "is_admin": user.is_admin}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@auth_router.post("/create-admin")
async def create_admin_user(username: str, password: str, db: AsyncSession = Depends(get_db)):
    """创建管理员用户 (仅在初始设置时使用，实际应用中应移除或严格限制访问)"""
    # 检查用户是否已存在
    query = select(models.User).filter(models.User.username == username)
    result = await db.execute(query)
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    
    # 创建新管理员用户
    hashed_password = get_password_hash(password)
    new_user = models.User(
        username=username,
        hashed_password=hashed_password,
        is_admin=1  # 设置为管理员
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return {"message": f"Admin user {username} created successfully"}

# GitHub OAuth登录路由
@auth_router.get("/github/login")
async def github_login(request: Request):
    """
    GitHub登录入口点
    重定向用户到GitHub授权页面
    """
    # 生成状态参数和认证URL
    auth_url = GitHubOAuth.get_auth_url()
    return RedirectResponse(url=auth_url)

@auth_router.get("/github/callback")
async def github_callback(code: str, state: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """
    GitHub OAuth回调处理
    处理用户从GitHub返回的授权
    """
    try:
        # 交换授权码获取访问令牌
        token_response = await GitHubOAuth.exchange_code(code)
        access_token = token_response.get('access_token')
        
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get access token from GitHub"
            )
        
        # 获取GitHub用户信息
        github_user = await GitHubOAuth.get_user_info(access_token)
        
        # 获取或创建系统用户
        user = await get_or_create_github_user(github_user, db)
        
        # 生成JWT访问令牌
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "is_admin": user.is_admin}, 
            expires_delta=access_token_expires
        )
          # 将用户重定向到前端并附带访问令牌
        # 在实际应用中，这可能会重定向到一个专门处理令牌存储的页面
        redirect_url = f"/index.html?token={access_token}"
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub OAuth process failed: {str(e)}"
        )

@auth_router.get("/user/me", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return current_user
