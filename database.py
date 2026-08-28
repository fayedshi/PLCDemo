
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings
from config import settings
import argparse

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base



# DATABASE_URL = "sqlite:///./crud_test.db"

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
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