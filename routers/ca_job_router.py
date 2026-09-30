
import asyncio
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.ca_job_model import CAJobModel

ca_job_router = APIRouter()

# 🚀 1. 核心后台状态机逻辑
async def run_ca_job_pipeline(job_id: int, delay_seconds: float):
    if delay_seconds > 0:
        print(f"⏰ [后台任务] 检测到定时时刻，将在内存中挂起等待 {delay_seconds} 秒...")
        await asyncio.sleep(delay_seconds) # 优雅挂起，不阻塞主线程
        
    # 到了时间，异步开启数据库连接执行后续的长控制
    async with async_session() as db:
        # 查询任务，如果发现被中途提前取消了 (status_code=4)，直接 return 终止
        # 否则更新状态为 1 (运行中)，读取时长参数，通过 asyncio.sleep 执行环流和排气...
        print(f"🎬 [后台任务] 时间已到，正式拉起 Job ID: {job_id}")
        # ...执行和之前类似的 PLC 读写和时长的 asyncio.sleep(...) 控制...

# 🚀 2. 接口调用
@ca_job_router.post("/jobs/launch")
async def launch_ca_job(payload: CAJobCreateSchema, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    # ...[省略前面的创建 db_job 逻辑]...
    
    # 计算时间差（秒）
    delay_seconds = 0.0
    if payload.plan_start_time and payload.plan_start_time > datetime.now():
        delay_seconds = (payload.plan_start_time - datetime.now()).total_seconds()
        
    # 🚀 直接丢给 FastAPI 的 background_tasks，程序会立刻给前端返回 200/201 成功响应
    background_tasks.add_task(run_ca_job_pipeline, db_job.id, delay_seconds)
    
    return {"status": "success", "message": "作业指令已成功下发至后台进程"}
