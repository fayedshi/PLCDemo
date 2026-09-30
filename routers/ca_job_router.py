# routers/ca_job_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

from database import get_db
from models import CAJobModel
from models import CAModuleModel # 之前的配置表

ca_job_router = APIRouter()

class CAJobCreateSchema(BaseModel):
    house_code: str
    mode_id: int
    plan_start_time: Optional[datetime] = None
    runtime_params: Dict[str, Any] # 前端加载好的完整40个字段快照

# 1. 下发/创建气调作业
@ca_job_router.post("/jobs/launch", status_code=status.HTTP_201_CREATED)
async def launch_ca_job(payload: CAJobCreateSchema, db: AsyncSession = Depends(get_db)):
    # 检查该仓房当前是否已有正在运行的作业，防止冲突
    stmt = select(CAJobModel).where(CAJobModel.house_code == payload.house_code, CAJobModel.status_code.in_([0, 1, 2]))
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"仓房 {payload.house_code} 当前已有激活的气调作业，无法重复启动！")

    # 查询模式名称
    mode_stmt = select(CAModuleModel.mode_name).where(CAModuleModel.id == payload.mode_id)
    mode_name = (await db.execute(mode_stmt)).scalar() or "未知模式"

    db_job = CAJobModel(
        house_code=payload.house_code,
        mode_id=payload.mode_id,
        mode_name=mode_name,
        plan_start_time=payload.plan_start_time,
        status_code=1 if not payload.plan_start_time else 0, # 如果没有计划时间，直接进入运行中
        status_text="运行中" if not payload.plan_start_time else "等待触发",
        start_time=datetime.now() if not payload.plan_start_time else None,
        runtime_params=payload.runtime_params
    )
    db.add(db_job)
    await db.commit()
    await db.refresh(db_job)
    # TODO: 异步拉起底层 asyncio.Lock 以及 PLC 通信状态机任务（类似你之前的 background_task）
    return {"status": "success", "job_id": db_job.id, "message": "作业指令下发成功"}

# 2. 控制作业状态（启动、暂停、中止）
@ca_job_router.post("/jobs/{job_id}/control")
async def control_ca_job(job_id: int, action: str, db: AsyncSession = Depends(get_db)):
    stmt = select(CAJobModel).where(CAJobModel.id == job_id)
    job = (await db.execute(stmt)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="未找到该作业记录")

    now = datetime.now()
    if action == "start":      # 暂停后重新启动，或将计划任务手动立刻拉起
        job.status_code, job.status_text = 1, "运行中"
        if not job.start_time: job.start_time = now
    elif action == "pause":    # 暂停
        job.status_code, job.status_text = 2, "已暂停"
    elif action == "stop":     # 中止
        job.status_code, job.status_text = 4, "被人为中止"
        job.end_time = now
    else:
        raise HTTPException(status_code=400, detail="非法的控制指令")
        
    job.update_time = now
    await db.commit()
    return {"status": "success", "current_status": job.status_text}
