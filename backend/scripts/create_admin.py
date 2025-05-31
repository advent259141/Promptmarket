#!/usr/bin/env python
# filepath: c:\Users\29684\Desktop\prompt_market\create_admin.py
import asyncio
import sys
import getpass
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 更改工作目录到项目根目录
os.chdir(project_root)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.models import Base, User
from app.api.auth import get_password_hash
from dotenv import load_dotenv
from sqlalchemy import text

# 加载环境变量
load_dotenv()

# 从.env文件读取数据库URI
DATABASE_URI = os.getenv("DATABASE_URL")
if not DATABASE_URI:
    print("错误: 未找到 DATABASE_URL 环境变量，请检查 .env 文件")
    sys.exit(1)

print(f"正在使用数据库: {DATABASE_URI}")

# 创建数据库引擎
engine = create_async_engine(DATABASE_URI, echo=True)
async_session = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

async def create_admin_user(username, password):
    """创建管理员用户"""
    try:
        async with async_session() as session:
            # 检查用户是否已存在
            result = await session.execute(
                text(f"SELECT * FROM users WHERE username = '{username}'")
            )
            user = result.fetchone()
            if user:
                print(f"用户 {username} 已存在!")
                return False
            
            # 创建新用户
            hashed_password = get_password_hash(password)
            await session.execute(
                text(f"INSERT INTO users (username, hashed_password, is_admin) VALUES ('{username}', '{hashed_password}', 1)")
            )
            await session.commit()
            print(f"管理员用户 {username} 创建成功!")
            return True
    except Exception as e:
        print(f"创建用户时发生错误: {str(e)}")
        return False

async def main():
    """主函数"""
    print("=== 创建管理员用户 ===")
    
    # 获取用户名和密码
    username = input("请输入管理员用户名: ")
    password = getpass.getpass("请输入密码: ")
    confirm_password = getpass.getpass("请确认密码: ")
    
    # 检查两次密码是否一致
    if password != confirm_password:
        print("错误: 两次输入的密码不一致!")
        return
    
    # 创建管理员用户
    success = await create_admin_user(username, password)
    if success:
        print("管理员用户创建成功！可以使用此账号登录管理系统。")

if __name__ == "__main__":
    asyncio.run(main())
