from fastapi import Depends, HTTPException,status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from enums.enum_user_role import UserRole
import database
import models
import random


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
SECRET_KEY = "GRAIN_ELEVATOR_SUPER_SECRET_KEY"
ALGORITHM = "HS256"

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录凭证已失效",
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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


def is_admin(token: str = Depends(oauth2_scheme)):
    try:
        # print(f'token {token}')
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期")
    # print(f'payload {payload}')
    role = payload.get("role")
    if role and role in (UserRole.SUPER_ADMIN.name,UserRole.ADMIN.name):
        return payload
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足，仅限管理员操作")



def generate_password():
    chars = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz23456789!@#$%^&*"
    return "".join(random.choices(chars, k=8))

# 测试输出
print(generate_password()) # 例如: "pB3#7mG$"
    