
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings
# from config import settings
import argparse
from sqlalchemy.engine import URL
import yaml


import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base


with open('dev.yaml', 'r', encoding='utf-8') as file:
    # 2. 使用 yaml.safe_load 读取文件内容
    config_data = yaml.safe_load(file)

# 查看读取出来的 Python 字典
print(config_data)

# 像操作普通字典一样读取数据
print(config_data['database']['password'])  # 输出: localhost
print(config_data['tags'][0])     

# DATABASE_URL = "sqlite:///./crud_test.db"

url_object = URL.create(
    drivername="mysql+aiomysql",
    username=config_data['database']['user'],
    password=config_data['database']['password'], # 包含特殊字符的原生密码
    host=config_data['database']['host'],
    port=int(config_data['database']['port']),
    database=config_data['database']['db_name'],
    query={"charset": "utf8mb4"}
)


engine = create_async_engine(url_object, echo=False, pool_pre_ping=True,  pool_size=10)
# SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

# 依赖项：获取数据库会话
async def get_db():
    # db = SessionLocal()
    try:
        async with AsyncSessionLocal() as session:
            yield session
    finally:
        await session.close()