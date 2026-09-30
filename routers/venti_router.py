import asyncio

from fastapi import APIRouter, HTTPException, Depends, Request, status, Query
from sqlalchemy import select, update, delete
from typing import List
import models, schemas
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from services.venti_service import VentiConfigService
from util import get_reg_start_addr, convert_dev_addr

from fastapi import APIRouter, BackgroundTasks, Query, Request, WebSocket
import asyncio

from sqlalchemy import desc, select 
from config import settings

from database import AsyncSessionLocal
from models import VentiTask
from schemas import VentiTaskCreate, VentiTaskResponse, VentiTaskUpdate

from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from logger.demo_logger import logger

router = APIRouter()


# 🎯 接口 1：【查】- 获取并筛选廒间列表（支持前端多条件过滤）

@router.get("/api/ventilation-modes", response_model=schemas.VentilationModePageResult)
async def get_venti_list(
    # house_code: Optional[int] = Query(None),
    # severity: Optional[str] = Query(None),
    # start_time: Optional[datetime] = Query(None),
    # end_time: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    # 🎯 注入我们的 Service 层
    service: VentiConfigService = Depends(VentiConfigService)
):
    try:
        # 🚀 路由层变得极其干净，只负责调用 Service 并传递参数
        items, total = await service.get_ventilation_modes(
           
            page=page,
            size=size
            # page=page, size=size
        )
        # logger.info('alarms, ', alarms)
        return {
            "total": total,
            "items": items
        }
    except Exception as e:
        logger.info(f"Service 层执行异常: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统内部业务处理异常"
        )


# 🎯 接口 2：【增】- 新增廒间
@router.post("/api/ventilation-mode", response_model=schemas.VentilationModeOut, status_code=status.HTTP_201_CREATED)
async def create_granary(obj_in: schemas.VentilationModeCreate, db: AsyncSession = Depends(get_db)):
    # 校验编号唯一性
    # check_stmt = select(models.VentilationMode).where(models.VentilationMode.code == obj_in.code)
    # existing = (await db.execute(check_stmt)).scalar_one_or_none()
    # if existing:
    #     raise HTTPException(status_code=400, detail="该廒间编号已存在，请勿重复添加")
    logger.info('in create venti-mode')
    new_venti_mode = models.VentilationMode(**obj_in.model_dump())
    db.add(new_venti_mode)
    await db.commit()
    await db.refresh(new_venti_mode)
    return new_venti_mode


# 🎯 接口 3：【改】- 依据 ID 修改廒间信息
@router.patch("/api/ventilation-mode/{item_id}", response_model=schemas.VentilationModeOut)
async def update_granary(request: Request, item_id: int, obj_in: schemas.VentilationModeUpdate, db: AsyncSession = Depends(get_db)):
    # 查询是否存在
    logger.info('####查询模式信息')
    stmt = select(models.VentilationMode).where(models.VentilationMode.id == item_id)
    db_item = (await db.execute(stmt)).scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="未找到该廒间记录")
        
    # 执行更新
    await db.execute(
        update(models.VentilationMode)
        .where(models.VentilationMode.id == item_id)
        .values(**obj_in.model_dump(exclude={"code"})) # 工业常识：禁止通过此接口修改主键 code
    )
    await db.commit()
    await db.refresh(db_item)

    # 同时更新内存中temp threshold
    # request.app.state.TEMP_UPPER_LIMIT = obj_in.max_temp
    logger.info(f'【已更新模式{obj_in.start_humidity_diff}温度上限值】为{obj_in.end_humidity_diff}')
    return db_item


# 🎯 接口 4：【删】- 依据 ID 删除廒间
@router.delete("/api/ventilation-mode/{item_id}")
async def delete_granary(item_id: int, db: AsyncSession = Depends(get_db)):
    logger.info('删除仓房信息')
    stmt = select(models.VentilationMode).where(models.VentilationMode.id == item_id)
    db_item = (await db.execute(stmt)).scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="未找到该廒间记录")
        
    await db.execute(delete(models.VentilationMode).where(models.VentilationMode.id == item_id))
    await db.commit()
    return {"status": "success", "msg": f"成功删除 ID 为 {item_id} 的廒间"}


@router.websocket("/ws/dev-state/{house_code}")
async def websocket_dev_state_endpoint(websocket: WebSocket, house_code):
    # global dev_state_cache
    await websocket.accept()
    logger.info("【后端提示】发现/ws/dev-state前端客户端已连接！")
    try:
        house_index = int(house_code) -1
        # house_config= load_silo_addrs(house_code)  
        # dev_start= house_config['devices_addr']['window-state'][0]

        dev_start= get_reg_start_addr(settings.granaries[house_index],'mode-display')
        logger.info(f'dev_start: {dev_start}')
        plc_client=websocket.app.state.plc_conns[house_index]
        while True:
            read_plc_func=websocket.app.state.partial_read
            dev_state_cache = await read_plc_func(plc_client,dev_start,34)
            await websocket.send_json(dev_state_cache)
            # send to vue every 2 sec
            await asyncio.sleep(1)
    except Exception as e:
        logger.info(f"ws/dev-state house-{house_code}客户端断开连接 : {e}")



#  控制接口
@router.post("/api/dev/control")
async def control_window(request: Request, data: dict):
    action_type = data.get('action_type')
    dev_id=data.get('dev_id')
    house_index = int(data.get('house_code')) -1
    logger.info(f'准备写入设备id {dev_id} , action_type: {action_type}')
    plc_lock = request.app.state.plc_locks[house_index]
    # todo: 枷锁精确到某个设备
    if plc_lock.locked():
        return {
            "status": "busy", 
            "message": f"仓房{house_index+1} 正处于通风作业中，请稍后再试！"
        }
    async with plc_lock:
        try:
            plc_client=request.app.state.plc_conns[house_index]
            if dev_id:
                dev_info = dev_id.split('-')
                await request.app.state.write_single_reg(plc_client,int(dev_info[1]), action_type)
                logger.info(f'写入PLC成功，设备id {dev_id}，动作 {action_type}')
            else:
                # batch devices
                batch_dev_address={'window':31,'door':32}
                category_type = data.get('category_type')
                await request.app.state.write_single_reg(plc_client, batch_dev_address[category_type], action_type)
                logger.info(f'写入PLC全控设备{category_type}成功')
        except Exception as e:
            logger.info(f"/api/dev/control 写入PLC异常: {e}")
        return {"status":"success"}


@router.post("/api/venti/adhoc/start")
async def venti_adhoc_start(request: Request, data: dict, background_tasks: BackgroundTasks):
       
    house_code = data.get('house_code')
    house_index = int(house_code) - 1
    # 获取该仓房对应的业务大锁
    logger.info(f'house-{house_code}【路由】收到前端 adhoc 启动请求') 
    plc_lock = request.app.state.plc_locks[house_index]
    logger.info(f'plc_lock: {plc_lock}')
    
    # 检查硬件当前是否正忙（如果锁着，说明有作业在开、在等或者在关）
    if plc_lock.locked():
        return {
            "status": "busy", 
            "message": f"仓房 {house_code} 的通风作业正在运行中，请勿重复操作！"
        }
        
    # 初始化作业取消标志为 False（必须在接口层立刻重置，防止上一次的取消信号残留）
    request.app.state.is_job_cancelled[house_index] = False
    # 🔥 核心改变：把原本沉重的 try...finally 一整套大流程，丢进 FastAPI 的后台线程队列
    background_tasks.add_task(background_venti_adhoc_job, request, data, house_index)
    # 立即给前端返回响应
    return {
        "status": "success",
        "message": f"仓房 {house_code} 即时作业已开启，预计运行时长 {data.get('duration')/60} 分钟。"
    }


async def background_venti_adhoc_job(request: Request, data: dict, house_index: int):
    # 初始化要写入数据库的状态字典
    task_data = {}
    venti_task_id = 0
    # 动态获取当前仓房的专属业务锁
    plc_lock = request.app.state.plc_locks[house_index]
    
    # 整个“开-等-关”全套动作上大锁，期间该仓房不允许任何其他指令插队
    async with plc_lock:
        logger.info(f'【后台】仓房 {house_index + 1} 成功获取业务大锁，准备开始作业...')
        try:
            # 步骤 A：向数据库插入初始运行记录
            init_data = {
                'house_code': data.get('house_code'), 
                'mode_name': None,  
                'mode_id': -1, 
                'status_code': 0,
                'status_text': '运行中',
                'create_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            # 假设 persist_venti_task 是一个异步的数据库写入函数
            venti_task_id = await persist_venti_task(init_data)
            logger.info(f'【后台】已新增数据库记录 venti_task_id: {venti_task_id}')
            
            # 步骤 B：调用您原有的 run_job 执行开启和计时维持（内部包含了 45 秒和轮询）
            # 注意：因为外面包裹了 async with plc_lock，run_job 内部的 write_single_reg 会极速通过，绝不冲突
            flag = await run_job(request, data)
            logger.info(f'【后台】run_job 运行完成，返回 flag : {flag}')
            if flag == 0:
                task_data['status_code'] = 1
                task_data['status_text'] = '正常结束'
                logger.info(f"【后台】已保持 {data.get('duration')} 分钟，准备复位关闭")
            else:
                task_data['status_code'] = 4
                task_data['status_text'] = '被取消'
                logger.info(f"【后台】作业被外部信号中止，准备复位关闭")
                
        except Exception as e:
            logger.info(f'【后台】作业运行期间发生异常: {e}')
            task_data['status_code'] = 5
            task_data['status_text'] = '异常中止'
            
        finally:
            # 步骤 D：无论中间是正常完工、被取消还是抛异常，一律在锁内执行复位关闭
            logger.info(f'【后台】开始执行 finally 设备复位清算...')
            task_data['update_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                # 执行关闭命令
                await stop_job(request, data)
                # logger.info(f'house {house_index +1} 【后台】执行关闭命令完毕，等待 45s 待设备完全关闭')
                # 保持锁，等待设备物理完全关闭
                await asyncio.sleep(45)
            except Exception as stop_err:
                logger.info(f'house {house_index +1}【后台】致命：安全关闭指令下发失败!! {stop_err}')
            
            # 步骤 E：更新最终的数据库记录
            if venti_task_id > 0:
                try:
                    await update_venti_task(venti_task_id, task_data)
                    logger.info(f'【后台】成功更新数据库最终状态为: {task_data["status_text"]}')
                except Exception as db_err:
                    logger.info(f'【后台】更新数据库状态失败: {db_err}')
        logger.info(f"【后台】仓房 {house_index + 1} 整个作业流安全退出，大锁已释放。")

# 0: completed normally, 1: cancelled, 2: timeout, 3: terminated abnormally
async def run_job(request: Request, data: dict):
    try:
        devices = data.get('devices')
        duration= data.get('duration')
        house_code=data.get('house_code')
        action_obj= convert_dev_addr(devices, house_code, 1)
        logger.info(f'house {house_code} start action obj: {action_obj}')
        await execute_commands(request, action_obj, house_code)
        logger.info(f'house {house_code} 执行开启命令完毕， 先等待45s待设备完全开启')
        await asyncio.sleep(45)
        
        elapsed=0
        house_index = int(house_code) -1
        # sleep minor amount of time
        while True:
            if elapsed < duration:
                logger.info(f'house {house_code} 保持状态计时，累计睡眠：{elapsed}')
                await asyncio.sleep(5)
                elapsed += 5
            else:
                logger.info(f'已达到运行时长限制：{duration}')
                return 0
            if request.app.state.is_job_cancelled[house_index]:
                logger.info(f"仓房{data.get('house_code')}作业被中止")
                # todo: update job record status as terminated
                return 1
    except asyncio.CancelledError:
        logger.info('run_job() got CancelledError, pass')
    except Exception as e:
        logger.info(f'run_job异常:{e}')
        raise e
        

# restore devices
async def stop_job(request: Request, data: dict):
    devices = data.get('devices')
    action_obj = convert_dev_addr(devices,data.get('house_code'), 0)
    logger.info(f"house-{data.get('house_code')} action_obj: {action_obj}")
    await execute_commands(request, action_obj, data.get('house_code'))
    logger.info(f"house-{data.get('house_code')} executed stop job commands")


async def persist_venti_task(task_data: dict):
    # 1. 使用 Pydantic 进行第一轮严格的数据校验和清洗
    try:
        validated_data = VentiTaskCreate(**task_data)
    except Exception as e:
        logger.info(f"❌ 报警数据格式校验失败: {e}")
        raise e

    # 2. 数据库会话上下文管 理
    async with AsyncSessionLocal() as session:
        try:
            # 3. 将校验通过的数据转化为 SQLAlche0my 的模型实例
            # model_dump() 会把 Pydantic 对象变回 Python 字典（老版本 Pydantic 请用 .dict()）
            db_venti_task = VentiTask(**validated_data.model_dump())
            logger.info(f'db_venti_task: {db_venti_task}')
            # 4. 执行插入并提交
            session.add(db_venti_task)
            await session.commit()
            logger.info(f"💾 venti task已成功持久化到MySQL，自增 ID: {db_venti_task.id}")
            return db_venti_task.id
        except Exception as e:
            await session.rollback()
            logger.info(f"❌ venti task入库失败，已自动回滚: {e}")
            raise e



async def update_venti_task(task_id: int, task_data: dict):
    """
    更新通风作业的异步方法
    :param task_id: 需要更新的作业主键 ID
    :param task_data: 前端传过来的修改字段字典 (例如: {"status_code": 2, "status_text": "运行中"})
    """
    # 1. 使用 Pydantic 进行第一轮严格的数据校验和清洗
    try:
        # 🚀 关键点：使用 VentiTaskUpdate 模型，它里面所有的字段都是 Optional 的
        validated_data = VentiTaskUpdate(**task_data)
    except Exception as e:
        logger.info(f"❌ 更新数据格式校验失败: {e}")
        return False

    # 2. 数据库会话上下文管理
    async with AsyncSessionLocal() as session:
        try:
            # 3. 🚀 关键步骤：先去数据库里查出这条已经存在的数据
            result = await session.execute(select(VentiTask).where(VentiTask.id == task_id))
            db_venti_task = result.scalars().first()
            
            if not db_venti_task:
                logger.info(f"⚠️ 未找到 ID 为 {task_id} 的通风作业，无法执行更新")
                return False

            # 4. 🚀 关键步骤：提取通过校验的数据字典
            # exclude_unset=True 的作用是：前端传了什么字段就只提取什么字段，
            # 没传的字段不会包含在内（防止把数据库里的旧数据误改成了 None）
            update_dict = validated_data.model_dump(exclude_unset=True)
            
            # 5. 动态将新值赋给查出来的 SQLAlchemy 模型对象
            for key, value in update_dict.items():
                setattr(db_venti_task, key, value)
                
            # 手动更新你的 update_time 字段（如果你的数据库没有设置 onupdate 自动更新的话）
            # db_venti_task.update_time = datetime.now()

            # 6. 执行提交
            await session.commit()
            logger.info(f"💾 venti task [ID: {task_id}] 已成功更新到 MySQL")
            return True
            
        except Exception as e:
            await session.rollback()
            logger.info(f"❌ venti task 更新失败，已自动回滚: {e}")
            return False

async def get_running_venti_tasks(house_code) -> List[VentiTaskResponse]:
    async with AsyncSessionLocal() as session:
        try:
            # 1. 构建查询语句：SELECT * FROM ventilation_jobs WHERE status_code = 5
            # 如果想按时间倒序排列，可以加上 .order_by(VentiTask.create_time.desc())
            stmt = select(VentiTask).where(VentiTask.status_code.in_ ([-1, 0]), VentiTask.house_code == house_code).order_by(desc(VentiTask.create_time))
            # 2. 异步执行查询
            result = await session.execute(stmt)
            # 3. 提取所有的 ORM 对象模型
            db_tasks = result.scalars().all()
            # 4. 利用 Pydantic 将 ORM 对象列表批量转换为响应模型列表
            
            # model_validate 配合列表推导式非常优雅且安全
            return [VentiTaskResponse.model_validate(task) for task in db_tasks]
            # return db_tasks
            
        except Exception as e:
            logger.info(f"❌ 查询任务列表失败: {e}")
            return []

@router.get("/api/venti/jobs/{house_code}")
async def venti_jobs(house_code:str):
    running_jobs =await get_running_venti_tasks(house_code)
    logger.info(f'running jobs {running_jobs}')
    return running_jobs


# 智能作业
#  任务状态： 等待触发（-1），运行中(0)，结束(1，正常完成 2，等待触发超时，3，等待结束超时， 4，cancelled  5，异常中止)
@router.post("/api/venti/sched/start")
async def venti_sched_start(request: Request, data: dict, background_tasks: BackgroundTasks):
    house_code = data.get('house_code')
    house_index = int(house_code) - 1
    plc_lock = request.app.state.plc_locks[house_index]
    # 检查硬件当前是否正忙（如果锁着，说明有作业在开、在等或者在关）
    if plc_lock.locked():
        return {
            "status": "busy", 
            "message": f"仓房 {house_code} 的通风智能作业正在运行中，请勿重复操作！"
        }
    logger.info(f'house {house_index +1}【路由】收到前端智能作业启动请求')    
    
    # 获取该仓房对应的业务大锁
    request.app.state.is_job_cancelled[house_index] =False
    background_tasks.add_task(background_venti_sched_task,request, data, house_index)
    return {
            "status": "success",
            "message": f"仓房 {house_code} 智能作业已开启，预计运行时长 {data.get('duration')/60} 分钟。"
        }

async def background_venti_sched_task(request, data, house_index):
    plc_lock = request.app.state.plc_locks[house_index]
    async with plc_lock:
        try:
            # 检查开始条件
            logger.info('开始智能作业')
            ret_code=0
            task_data={
                'house_code': data.get('house_code'),
                'mode_name': data.get('mode_name'), 
                'mode_id': data.get('mode_id'), 
                'status_code': -1 ,
                'status_text': '等待触发',
                'create_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            venti_task_id=await persist_venti_task(task_data)
            task_data={}
            check_start_condition_task= asyncio.create_task(check_condition(request, data, 0,  None))
            ret_code = await asyncio.wait_for(check_start_condition_task, settings.sched_max_wait)
            logger.info(f"ret {ret_code}")
            if ret_code==1:
                logger.info("等待中被人为中止，作业结束")
                task_data['status_code'] = 4
                task_data['status_text'] = '被取消'
            elif ret_code==2:
                task_data['status_code'] = 2
                task_data['status_text'] = '等待触发超时'
            # 条件满足，开始执行job
        except asyncio.TimeoutError:
            logger.info(f"【等待触发超时错误】: 任务等待触发超过了设定的 {settings.sched_max_wait} 分钟限制，已被强制终止！")
                # todo: update record status as waiting timeout
            task_data['status_code'] = 2
            task_data['status_text'] = '等待触发超时'
            ret_code=2
        except Exception as e:
            logger.info(f'等待开始条件发生异常:{e}')
            # todo: 
            ret_code=3
            task_data['status_code'] = 5
            task_data['status_text'] = '异常中止'
        finally:
            if ret_code:
                task_data['update_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                await update_venti_task(venti_task_id, task_data)
                logger.info(f"house {house_index +1}已更新数据库中作业状态 as {task_data['status_text']}")
                return
            else:
                logger.info(f'准备开启作业 house {house_index+1}')
        # 检查结束条件
        try:
            logger.info('检查结束条件')
            task_run_job= asyncio.create_task(run_job(request, data))
            check_end_condition_task =asyncio.create_task(check_condition(request, data, 1, task_run_job))

            task_data['status_code'] = 0
            task_data['status_text'] = '运行中'
            task_data['update_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await update_venti_task(venti_task_id, task_data)
            results = await asyncio.gather(task_run_job, check_end_condition_task, return_exceptions=True)
            if results[1]==0:
                task_data['status_code'] = 1
                task_data['status_text'] = '正常结束'
            elif results[1]==1:
                task_data['status_code'] = 4
                task_data['status_text'] = '被取消'
            elif results[1]==2:
                # timeout
                logger.info(f"【Job执行超时错误】: 作业运行超过了设定的 {data.get('duration')} 分钟限制，已被强制终止！")
                task_data['status_code'] = 3
                task_data['status_text'] =  '等待结束超时'
            else:
                task_data['status_code'] = 5
                task_data['status_text'] = '异常中止'
        # except asyncio.TimeoutError:
        #     logger.info(f"【Job执行超时错误】: 作业运行超过了设定的 {data.get('duration')} 分钟限制，已被强制终止！")
        #     # todo: update record status as running timeout
        except Exception as e:
            logger.info(f'Schedule job异常:{e}')
        finally:
            await stop_job(request, data)
            logger.info(f'house {house_index +1}执行关闭命令完毕，等待45s待设备完全关闭')
            await asyncio.sleep(45)
            task_data['update_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await update_venti_task(venti_task_id, task_data)
        
# mode 0: ConditionUpperSilo,  1: ConditionAccumulatedHeat,  2: ConditionWholeSilo,
# flag 0: start condition, 1: end condition
# 0: completed normally, 1: cancelled, 2: timeout, 3: terminated abnormally
async def check_condition(request, data, flag, task_run_job):
    house_index = int(data.get('house_code')) -1
    elapsed=0
    while True:
        logger.info(f'check_condition flag: {flag}, elsapsed: {elapsed}')
        elapsed += 5
        is_cond_met = await check_condition_by_mode(request,flag, data)
        if flag==0:
            if elapsed < settings.sched_max_wait:
                await asyncio.sleep(5)
            else:
                logger.info(f'house {house_index +1}超过最长等待触发时间')
                return 2
            if is_cond_met:
                # logger.info(f"house {house_index +1}满足开始条件")
                return 0
        else:
            if is_cond_met:
                logger.info(f'house {house_index +1}满足结束条件,等待10s后中止')
                await asyncio.sleep(10)
                task_run_job.cancel()
                logger.info('task_run_job cancelled')
                return 0
            if elapsed < data.get('duration'):
                logger.info(f'house {house_index +1}未满足结束条件，继续睡眠 5s')
                await asyncio.sleep(5)
                # mock for testing
                if elapsed > data.get('duration') -10:
                    data.get('end_condition')['maxMoisture']=105
                # mock for testing
            else:
                logger.info(f"house {house_index +1}等待结束条件超时，cancel run_job")
                task_run_job.cancel()
                return 2
        if request.app.state.is_job_cancelled[house_index]:
            logger.info(f'house {house_index +1}收到中止信号，停止等待结束条件')
            task_run_job.cancel()
            return 1

            
async def check_condition_by_mode(request, flag, data):
    mode_id= data.get('mode_id')
    logger.info(f'check_condition_by_mode, mode_id: {mode_id}')
    house_index = int(data.get('house_code')) -1
    sum=0
    for i in range(0, 140, 4):
        sum += request.app.state.global_display_temp_cache[house_index][i]
    surface_avg= round(sum/35,1)
    max_internal_humid = round(max(request.app.state.global_humid_cache[house_index])/10,1)
    logger.info(f"house {house_index +1} 当前仓内最大湿度:{max_internal_humid}，\
                表层平均温度：{surface_avg}， 仓外温度{request.app.state.external_temp[house_index]}, 睡眠30s \
                diff: {surface_avg - request.app.state.external_temp[house_index]}\
                start_maxMoisture {data.get('start_condition').get('maxMoisture')}， \
                start_minTotalTempDiff {data.get('start_condition').get('minTotalTempDiff')}，\
                end maxMoisture {data.get('end_condition').get('maxMoisture')}， \
                end minTotalTempDiff {data.get('end_condition').get('minTotalTempDiff')}"
                )
    if mode_id ==1:
        ext_temp = request.app.state.external_temp[house_index]    
        if flag ==0:
            if max_internal_humid >= data.get('start_condition').get('maxMoisture')  \
                and  surface_avg - ext_temp >= data.get('start_condition').get('minTotalTempDiff'):
                logger.info(f"house {house_index +1}满足开始条件")
                return True
        else:
            if max_internal_humid < data.get('end_condition').get('maxMoisture')  \
                    and  surface_avg - ext_temp < data.get('end_condition').get('minTotalTempDiff'):
                return True
    elif mode_id ==2:
        sum=0
        for i in range(3, 140, 4):
            sum += request.app.state.global_display_temp_cache[house_index][i]
        bottom_avg= round(sum/35,1)
        logger.info(f'bottom_avg: {bottom_avg}')
        if flag ==0:
            if max_internal_humid < data.get('start_condition').get('maxMoisture')  \
                and  surface_avg - bottom_avg >= data.get('start_condition').get('minTotalTempDiff'):
                logger.info(f"house {house_index +1} 满足开始条件")
                return True
        else:
            if max_internal_humid > data.get('end_condition').get('maxMoisture')  \
                or  surface_avg - bottom_avg < data.get('end_condition').get('minTotalTempDiff') \
                or bottom_avg >= data.get('end_condition').get('bottomGrainAvgTemp'):
                return True
    return False
            
@router.post("/api/venti/job/stop")
async def venti_adhoc_stop(request: Request, data: dict):
    # todo # if running jobs：
    # tasks= await get_running_venti_tasks(house_code)
    # logger.info(f'running tasks: {tasks}')
    house_code=data.get('house_code')
    house_index = int(house_code) -1
    plc_lock = request.app.state.plc_locks[house_index]
    if not plc_lock.locked():
        logger.info(f'house {house_index +1}当前无运行中的作业')
        # raise Exception('当前无运行中的作业')
        return {
            "status": "error",
            "message": f"仓房 {house_code} 当前没有正在运行的通风作业。"
        }
    if request.app.state.is_job_cancelled[house_index]:
        return {
            "status": "processing",
            "message": f"仓房 {house_code} 的停止指令之前已发出，系统正在响应并安全关闭设备，请耐心等待。"
        }
    request.app.state.is_job_cancelled[house_index] =True
    logger.info(f"house-{data.get('house_code')} 作业停止信号已发出")
    return {
        "status": "success",
        "message": f"仓房 {house_code} 的中止指令已下发。系统将自动执行设备复位关闭程序（关闭过程约需 45 秒）。"
    }
    

async def execute_commands(request, action_obj, house_code):
    house_index = int(house_code) -1
    plc_client = request.app.state.plc_conns[house_index]
    # target_keys = ['blowers', 'exhaustFans']
    if 'dampers' in action_obj and action_obj['dampers']:
            # oper dampers first
            # damper_keys=[]
        for key,val in action_obj['dampers'].items():
            logger.info(f'writing to dampers at {key}')
            await request.app.state.write_single_reg(plc_client, int(key), val)
                # await write_single_step(plc_client, key,val)
        logger.info(f'waiting for dampers to open/close fully')
        await asyncio.sleep(45)

    for key in action_obj.keys():
        if key=='dampers':
            continue
        act_vals=action_obj.get(key)
        for key, move in act_vals.items():
            await request.app.state.write_single_reg(plc_client, int(key), move)
            await asyncio.sleep(0.05) # 微小延时
    # todo: shutdown dampers first

    
# async def stop_adhoc(request, action_obj, house_code):
#     house_index = int(house_code) -1
#     plc_client = request.app.state.plc_conns[house_index]
#     for key, value in action_obj.items():
#         await request.app.state.write_single_reg(plc_client, int(key), value)
   

#  flag 1: start job, 0: stop job
#  convert the address from ui to the json of register address and value

            
