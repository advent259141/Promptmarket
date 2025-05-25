from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv() # 加载 .env 文件中的环境变量

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+aiomysql://user:password@localhost/prompt_market_db")

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def create_tables():
    """创建数据库表并进行必要的迁移"""
    from sqlalchemy import text
    
    # 创建所有表（如果不存在）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # 检查 prompts 表中是否已存在 status 列
        try:
            result = await conn.execute(text("SHOW COLUMNS FROM `prompts` LIKE 'status'"))
            column_exists = result.fetchone() is not None
            
            # 如果status列不存在，则添加它
            if not column_exists:
                print("正在添加status列...")
                await conn.execute(text("ALTER TABLE `prompts` ADD COLUMN `status` INTEGER DEFAULT 0"))
                print("status列已成功添加")
                
                # 默认将所有现有prompt设为已通过状态(1)
                print("正在将现有prompt状态设为已通过...")
                await conn.execute(text("UPDATE `prompts` SET `status` = 1"))
                print("现有prompt状态已更新")
            else:
                print("status列已存在，无需修改")
                
            # 检查 prompts 表中是否已存在 views 列
            result = await conn.execute(text("SHOW COLUMNS FROM `prompts` LIKE 'views'"))
            views_column_exists = result.fetchone() is not None
            
            # 如果views列不存在，则添加它
            if not views_column_exists:
                print("正在添加views列...")
                await conn.execute(text("ALTER TABLE `prompts` ADD COLUMN `views` INTEGER DEFAULT 0"))
                print("views列已成功添加")
            else:
                print("views列已存在，无需修改")
                
            # 检查是否已存在 notifications 表
            result = await conn.execute(text("SHOW TABLES LIKE 'notifications'"))
            notifications_table_exists = result.fetchone() is not None
            
            if not notifications_table_exists:
                print("正在创建notifications表...")
                # notifications表会通过create_all自动创建
                print("notifications表已成功创建")
            else:
                print("notifications表已存在，无需修改")
                
        except Exception as e:
            print(f"迁移过程中出错: {e}")
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # 开发时使用，清空表
        await conn.run_sync(Base.metadata.create_all)
