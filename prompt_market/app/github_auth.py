"""
GitHub OAuth 辅助函数和类
"""
import httpx
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from . import models, config, schemas
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import secrets
import string

class GitHubOAuth:
    """处理GitHub OAuth认证的类"""
    
    @staticmethod
    def get_auth_url(state: Optional[str] = None) -> str:
        """
        生成GitHub OAuth认证URL
        
        :param state: 可选的状态参数，用于防止CSRF攻击
        :return: 授权URL
        """
        if not state:
            # 生成一个随机状态字符串
            chars = string.ascii_letters + string.digits
            state = ''.join(secrets.choice(chars) for _ in range(40))
            
        params = {
            'client_id': config.GITHUB_CLIENT_ID,
            'redirect_uri': config.GITHUB_REDIRECT_URI,
            'scope': 'read:user user:email',  # 请求访问用户信息和电子邮件
            'state': state
        }
        
        # 构建查询字符串
        query_string = '&'.join(f"{k}={v}" for k, v in params.items())
        return f"https://github.com/login/oauth/authorize?{query_string}"
    
    @staticmethod
    async def exchange_code(code: str) -> Dict[str, Any]:
        """
        使用授权码获取访问令牌
        
        :param code: GitHub返回的授权码
        :return: 包含访问令牌的字典
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://github.com/login/oauth/access_token',
                data={
                    'client_id': config.GITHUB_CLIENT_ID,
                    'client_secret': config.GITHUB_CLIENT_SECRET,
                    'code': code,
                    'redirect_uri': config.GITHUB_REDIRECT_URI
                },
                headers={'Accept': 'application/json'}
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"GitHub token exchange failed: {response.text}"
                )
                
            return response.json()
    
    @staticmethod
    async def get_user_info(access_token: str) -> schemas.GitHubUser:
        """
        使用访问令牌获取GitHub用户信息
        
        :param access_token: GitHub访问令牌
        :return: GitHub用户信息
        """
        async with httpx.AsyncClient() as client:
            # 获取用户基本信息
            response = await client.get(
                'https://api.github.com/user',
                headers={
                    'Authorization': f'token {access_token}',
                    'Accept': 'application/json'
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"Failed to fetch GitHub user info: {response.text}"
                )
                
            user_data = response.json()
            
            # 获取用户电子邮件地址(如果用户授权了email权限)
            if 'email' not in user_data or not user_data['email']:
                email_response = await client.get(
                    'https://api.github.com/user/emails',
                    headers={
                        'Authorization': f'token {access_token}',
                        'Accept': 'application/json'
                    }
                )
                
                if email_response.status_code == 200:
                    emails = email_response.json()
                    # 找到主要且已验证的邮箱
                    primary_email = next((e for e in emails if e.get('primary') and e.get('verified')), None)
                    if primary_email:
                        user_data['email'] = primary_email['email']
            
            return schemas.GitHubUser(
                id=user_data['id'],
                login=user_data['login'],
                avatar_url=user_data.get('avatar_url'),
                name=user_data.get('name'),
                email=user_data.get('email')
            )

async def get_or_create_github_user(github_user: schemas.GitHubUser, db: AsyncSession) -> models.User:
    """
    根据GitHub用户信息获取或创建用户
    
    :param github_user: GitHub用户信息
    :param db: 数据库会话
    :return: 系统用户对象
    """
    # 查找是否已存在使用GitHub登录的用户
    query = select(models.User).filter(
        models.User.oauth_provider == 'github',
        models.User.oauth_id == str(github_user.id)
    )
    result = await db.execute(query)
    user = result.scalars().first()
    
    if user:
        # 找到现有用户，更新信息
        if github_user.avatar_url:
            user.avatar_url = github_user.avatar_url
        if github_user.email and not user.email:
            user.email = github_user.email
        
        await db.commit()
        await db.refresh(user)
        return user
    
    # 检查是否存在使用相同用户名的账户
    username = github_user.login
    
    # 检查用户名是否已被使用
    query = select(models.User).filter(models.User.username == username)
    result = await db.execute(query)
    existing_username = result.scalars().first()
    
    # 如果用户名存在，添加随机后缀
    if existing_username:
        random_suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
        username = f"{username}_{random_suffix}"
    
    # 创建新用户
    new_user = models.User(
        username=username,
        email=github_user.email,
        oauth_provider='github',
        oauth_id=str(github_user.id),
        avatar_url=github_user.avatar_url,
        is_admin=0  # 新创建的GitHub用户不是管理员
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user
