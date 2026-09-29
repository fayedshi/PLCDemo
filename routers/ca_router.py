# routers/ca_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

# 导入你之前定义的数据库配置、Model和Schema
# 💡 请根据你项目的实际目录结构修改导入路径
from database import get_db  # 假设你有一个提供 db 会话的依赖函数
import models, schemas
# from models.ca_model import CAModuleModel
# from schemas.ca_schema import CACreate, CAUpdate, CAResponse

# 🚀 声明气调模块的路由器
ca_router = APIRouter()

# ==========================================
# 1. 查 - 获取所有气调配置列表 (GET)
# ==========================================
@ca_router.get("/configs", response_model=List[schemas.CAResponse], summary="获取所有气调配置列表")
async def get_ca_configs(db: Session = Depends(get_db)):
    # 从数据库查询所有配置，按 ID 倒序排列
    configs = db.query(models.CAModuleModel).order_code(models.CAModuleModel.id.desc()).all()
    # 🚀 即使数据库是空的，这里也会返回标准的空数组 `[]`，绝不会让前端报 DOCTYPE 错误
    return configs


# ==========================================
# 2. 增 - 创建新的气调配置 (POST)
# ==========================================
@ca_router.post("/configs", response_model=schemas.CAResponse, status_code=status.HTTP_201_CREATED, summary="创建气调配置")
async def create_ca_config(payload: schemas.CACreate, db: Session = Depends(get_db)):
    # 将 Pydantic 接收到的 DTO 数据转换为 SQLAlchemy 模型对象
    # payload.dict() 会自动包含核心参数和 26 个阀门的状态
    db_config = models.CAModuleModel(**payload.dict())
    
    db.add(db_config)
    db.commit()
    db.refresh(db_config) # 刷新以获取自增的 ID
    return db_config


# ==========================================
# 3. 改 - 修改现有的气调配置 (PUT)
# ==========================================
@ca_router.put("/configs/{config_id}", response_model=schemas.CAResponse, summary="更新气调配置")
async def update_ca_config(config_id: int, payload: schemas.CAUpdate, db: Session = Depends(get_db)):
    # 1. 先查出原数据是否存在
    db_config = db.query(models.CAModuleModel).filter(models.CAModuleModel.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail=f"未找到 ID 为 {config_id} 的气调配置")
    
    # 2. 动态更新字段（排除未传的字段，保留原有的未改动数据）
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_config, key, value)
        
    db_config.update_time = datetime.now() # 手动触发更新时间
    
    db.commit()
    db.refresh(db_config)
    return db_config


# ==========================================
# 4. 删 - 删除指定的气调配置 (DELETE)
# ==========================================
@ca_router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除气调配置")
async def delete_ca_config(config_id: int, db: Session = Depends(get_db)):
    db_config = db.query(models.CAModuleModel).filter(models.CAModuleModel.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail=f"未找到 ID 为 {config_id} 的气调配置")
        
    db.delete(db_config)
    db.commit()
    # 204 No Content 规范下不需要返回任何 JSON 主体内容
    return None
