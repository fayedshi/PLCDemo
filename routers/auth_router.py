# JWT 配置
from fastapi import APIRouter, FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta
from typing import List

import models, schemas, database
from logger.demo_logger import logger

SECRET_KEY = "GRAIN_ELEVATOR_SUPER_SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480 # 8小时，适合工厂值班排班

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


router = APIRouter()
# 工具函数
def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password, hashed_password)

def get_password_hash(password):
    return password_hash.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# 依赖项：获取当前登录用户,     # Depends(oauth2_scheme) 会自动去 Header 里找 Bearer Token
async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录凭证已失效",
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.info(f'payload: {payload}')
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    stmt = select(models.User).where(models.User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user

# 依赖项：验证管理员权限
def check_admin(current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="权限不足，仅限管理员操作")
    return current_user

# --- 路由实现 ---

# 1. 初始化默认管理员（如果数据库为空）
# @router.on_event("startup")


# 2. 登录接口
@router.post("/api/login", response_model=schemas.Token)
async def login(form_data: schemas.UserCreate, db: AsyncSession = Depends(database.get_db)):

    # stmt = select(CAModuleModel).where(CAModuleModel.id == config_id)
        
    # result = await db.execute(stmt)

    # stmt = select(CAModuleModel).where(CAModuleModel.id == config_id)
    #     result = await db.execute(stmt)
    # db_config = 
        
    stmt = select(models.User).where(models.User.username == form_data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}

# 3. 用户列表（仅管理员）
@router.get("/api/users", response_model=List[schemas.UserOut])
async def get_users(db: AsyncSession = Depends(database.get_db), current_user = Depends(check_admin)):
    stmt = select(models.User).order_by(models.User.id.desc())
    result = await db.execute(stmt)
    # scalars().all() 获取对象列表，若为空则自动返回空数组 `[]`
    users = result.scalars().all()
    return users

    # return db.query(models.User).all()

# 4. 创建用户（仅管理员）
@router.post("/api/users", response_model=schemas.UserOut)
async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(database.get_db), current_user: models.User = Depends(check_admin)):
    stmt = select(models.User).where(models.User.username == user.username)
    result = await db.execute(stmt)
        # scalars().all() 获取对象列表，若为空则自动返回空数组 `[]`
    db_user = result.scalars().first()
    if db_user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    new_user = models.User(
        username=user.username,
        hashed_password=get_password_hash(user.password),
        role=user.role
    )
    # db.add(new_user)
    # db.commit()
    # db.refresh(new_user)

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user) 
    return new_user

# 5. 删除用户（仅管理员）
@router.delete("/api/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(database.get_db), current_user: models.User = Depends(check_admin)):
    # user = db.query(models.User).filter(models.User.id == user_id).first()
    stmt = select(models.User).where(models.User.id == user_id)
    result = await db.execute(stmt)
            # scalars().all() 获取对象列表，若为空则自动返回空数组 `[]`
    user = result.scalars().first()

    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.username == "admin":
        raise HTTPException(status_code=400, detail="系统内置超级管理员不能删除")
    stmt = delete(models.User).where(models.User.id == user_id)        
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"未找到 ID 为 {user_id} 的用户")
    await db.commit()
    return {"detail": "删除成功"}