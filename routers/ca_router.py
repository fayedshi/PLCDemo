# routers/ca_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from datetime import datetime

# 💡 请根据你项目的实际目录结构修改导入路径
# 确保你的 get_db 返回的是 AsyncSession 的生成器
from database import get_db  
from models import CAModuleModel
from schemas import CACreate, CAUpdate, CAResponse

# 🚀 声明气调模块的路由器
router = APIRouter(prefix='/api/ca')

# ==========================================
# 1. 查 - 获取所有气调配置列表 (GET)
# ==========================================
@router.get("/configs", response_model=List[CAResponse], summary="获取所有气调配置列表")
async def get_ca_configs(db: AsyncSession = Depends(get_db)):
    # 🚀 SQLAlchemy 2.0 异步标准写法：先构建 select 语句
    stmt = select(CAModuleModel).order_by(CAModuleModel.id.desc())
    
    # 执行异步查询
    result = await db.execute(stmt)
    
    # scalars().all() 获取对象列表，若为空则自动返回空数组 `[]`
    configs = result.scalars().all()
    return configs


# ==========================================
# 2. 增 - 创建新的气调配置 (POST)
# ==========================================
@router.post("/configs", response_model=CAResponse, status_code=status.HTTP_201_CREATED, summary="创建气调配置")
async def create_ca_config(payload: CACreate, db: AsyncSession = Depends(get_db)):
    # 将 Pydantic DTO 数据转换为模型对象
    # 在 Pydantic v2 中推荐使用 payload.model_dump()，如果是 v1 请用 payload.dict()
    db_config = CAModuleModel(**payload.model_dump())
    
    db.add(db_config)
    # 🚀 异步提交与刷新
    await db.commit()
    await db.refresh(db_config) 
    return db_config


# ==========================================
# 3. 改 - 修改现有的气调配置 (PUT)
# ==========================================
@router.put("/configs/{config_id}", response_model=CAResponse, summary="更新气调配置")
async def update_ca_config(config_id: int, payload: CAUpdate, db: AsyncSession = Depends(get_db)):
    # 1. 异步查询原数据是否存在
    stmt = select(CAModuleModel).where(CAModuleModel.id == config_id)
    result = await db.execute(stmt)
    db_config = result.scalar_one_or_none()
    
    if not db_config:
        raise HTTPException(status_code=404, detail=f"未找到 ID 为 {config_id} 的气调配置")
    
    # 2. 动态更新字段
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_config, key, value)
        
    db_config.update_time = datetime.now() 
    
    # 🚀 异步提交与刷新
    await db.commit()
    await db.refresh(db_config)
    return db_config


# ==========================================
# 4. 删 - 删除指定的气调配置 (DELETE)
# ==========================================
@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除气调配置")
async def delete_ca_config(config_id: int, db: AsyncSession = Depends(get_db)):
    # 使用异步专用的 delete 语句执行删除，效率更高
    stmt = delete(CAModuleModel).where(CAModuleModel.id == config_id)
    
    result = await db.execute(stmt)
    
    # rowcount 可以获取实际删除的行数，用来判断数据是否存在
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"未找到 ID 为 {config_id} 的气调配置")
        
    await db.commit()
    return None
