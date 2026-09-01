
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings
from config import settings
import argparse
from sqlalchemy.engine import URL


import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base



# DATABASE_URL = "sqlite:///./crud_test.db"

url_object = URL.create(
    drivername="mysql+aiomysql",
    username=settings.DB_USER,
    password=settings.DB_PASSWORD, # 包含特殊字符的原生密码
    host=settings.DB_HOST,
    port=int(settings.DB_PORT),
    database=settings.DB_NAME,
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