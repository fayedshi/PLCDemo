from datetime import timedelta

from fastapi import APIRouter, Query, Request,WebSocket
import statistics
import asyncio

from sqlalchemy import select 
from config import settings
from config_loader import load_config
from influxdb_client_3 import InfluxDBClient3
import numpy as np
import pandas as pd

from database import AsyncSessionLocal
from date_util import to_utctime
from models import VentiTask
from schemas import AlarmLogResponse, VentiTaskBase, VentiTaskCreate, VentiTaskResponse, VentiTaskUpdate
from services.alarm_service import AlarmService

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status

from util import get_reg_start_addr
# from log.plc_logger import logger


router = APIRouter(tags=["web请求模块"])
batch_dev_address={'window':31,'door':32}


config_data=load_config()
granaries = config_data.get('granaries', [])

# 3. WebSocket 接口（用于向手机和本地 Vue 实时推送 Modbus 数据）
@router.websocket("/ws/live/{gran_code}")
async def websocket_endpoint(websocket: WebSocket, gran_code: str):
    
    await websocket.accept()
    print(f"【后端提示】/ws/live前端house-{gran_code}客户端已连接！")
    try:
        house_index = int(gran_code) -1
        # print('in live temp_cache: ',websocket.app.state.global_display_temp_cache[house_index])
        # print('in live humid_cache: ',websocket.app.state.global_humid_cache[house_index])
        websocket.app.state.read_temp_humid_interval[house_index]= 5
        websocket.app.state.read_power_interval[house_index]=5
        while True:
            # plc_data = global_display_temp_cache
            # print('in live ',global_plc_cache)
            # if not websocket.app.state.global_plc_cache[house_index]:
            #     await asyncio.sleep(2)
            #     continue
            # print('global_display_temp_cache in ws/live', websocket.app.state.global_power_cache[house_index])
            avg_temp=round(statistics.mean(websocket.app.state.global_display_temp_cache[house_index]),1)
            avg_humid=round(statistics.mean(websocket.app.state.global_humid_cache[house_index])/10,1)
            # websocket.app.state.global_power_cache
            send_buffer=websocket.app.state.global_power_cache[house_index][:4]
            # data=[avg_temp,avg_humid]
            send_buffer.extend([avg_temp,avg_humid])
            # print(data)
            await websocket.send_json(send_buffer)
            # send to vue every 2 sec
            await asyncio.sleep(5)
    except Exception as e:
        print(f"客户端/ws/live断开连接house-{gran_code}: {e}")
    finally:
        websocket.app.state.read_temp_humid_interval[house_index]= 300
        websocket.app.state.read_power_interval[house_index]=300


# 4. WebSocket 接口：供前端实时连接
@router.websocket("/ws/alarms")
async def websocket_alarms_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(f"客户端/ws/alarms已连接:")
    # connected_clients.add(websocket)
    try:
        # 不需要分仓房，本来就是收集多个仓房
        # house_index = int(house_code) -1
        websocket.app.state.read_alarm_interval= 2
        # manual execute once to expose alarms
        # websocket.app.state.check_temp_alarm('TEMP_HIGH', gran['code'], index)
        while True:
            # await websocket.receive_text() # 维持心跳
            # print(f'alarms: {websocket.app.state.active_alarms}')
            # 握手成功后，立刻把当前“正在发生”的报警推给前端，防止前端刷新页面后看板变空
            await websocket.send_json(
                websocket.app.state.active_alarms
            )
            await asyncio.sleep(2)
    except Exception as e:
        print(f"客户端/ws/alarms断开连接: {e}")
    finally:
        websocket.app.state.read_alarm_interval= 5

    # except WebSocketDisconnect:
        # connected_clients.remove(websocket)

# --- API 接口定义 ---
@router.get("/api/alarms/history", response_model=AlarmLogResponse)
async def get_history_alarms(
    house_code: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    # 🎯 注入我们的 Service 层
    service: AlarmService = Depends(AlarmService)
):
    try:
        # 🚀 路由层变得极其干净，只负责调用 Service 并传递参数
        alarms, alarms_total = await service.get_history(
            house_code=house_code,
            severity=severity,
            start_time=start_time,
            end_time=end_time,
            page=page,
            size=size
            # page=page, size=size
        )
        # print('alarms, ', alarms)
        return {
            "historyTotal": alarms_total,
            "items": alarms
        }
    except Exception as e:
        print(f"Service 层执行异常: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统内部业务处理异常"
        )

# todo: add house code
@router.websocket("/ws/dev-state/{house_code}")
async def websocket_dev_state_endpoint(websocket: WebSocket, house_code):
    # global dev_state_cache
    await websocket.accept()
    print("【后端提示】发现/ws/dev-state前端客户端已连接！")
    try:
        house_index = int(house_code) -1
        # house_config= load_silo_addrs(house_code) 
        # dev_start= house_config['devices_addr']['window-state'][0]

        dev_start= get_reg_start_addr(settings.granaries[house_index],'window-state')
        print(f'dev_start: {dev_start}')
        plc_client=websocket.app.state.plc_conns[house_index]
        while True:
            read_plc_func=websocket.app.state.partial_read
            dev_state_cache = await read_plc_func(plc_client,dev_start,32)
            await websocket.send_json(dev_state_cache)
            # send to vue every 2 sec
            await asyncio.sleep(1)
    except Exception as e:
        print(f"ws/dev-state house-{house_code}客户端断开连接 : {e}")



@router.get("/api/tempreport")
def show_cords_temp(request: Request, input_time: str):
    print('input_time', input_time)
    influx_client=InfluxDBClient3(host=request.app.state.influx_db_url, token=request.app.state.influx_token, database="my_db")
    
    # input_time = obj.get('input_time')
    # start_time = f"{input_time}:00Z"
    # dt_obj = datetime.fromisoformat(input_time)
    # new_dt_obj = dt_obj + timedelta(minutes=1)
    # end_time = new_dt_obj.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    temp_cols = [f"temp{i}" for i in range(140)]
    temp_all_cols = ", ".join(temp_cols)

    if not input_time:
        query = f"""
            SELECT {temp_all_cols},time FROM plc_temp_data 
            WHERE time >= NOW() - INTERVAL '1 day'
            order by time desc limit 1
            """
    else:
        start_time=to_utctime(input_time)
        query = f"""
            SELECT {temp_all_cols}, time 
            FROM plc_temp_data 
            WHERE time >= '{start_time}' 
            order by time asc
            limit 1
            """

    # 3. 执行查询并转换数据
    try:
        # language="sql" 显式指定使用 SQL引擎
        # print('to exectue',query)
        table = influx_client.query(query=query, language="sql")

        # 4. 将 PyArrow Table 转换为 Pandas DataFrame
        if table.num_rows == 0:
            return pd.DataFrame()
        # 将 PyArrow Table 转换为 Pandas DataFrame 以便后续分析
        df = table.to_pandas()
        print('found data\n',df)
        print(f"查询到 {len(df)} 条数据")
        # print('df.head: ',df.head())
        return df.to_dict(orient="records")[0]
    except Exception as e:
        print(f"查询失败: {e}")
    finally:
        influx_client.close()


@router.get("/api/temp-trend")
def get_history_data(request: Request,start_time: str,end_time: str, layer: int, options: list[str] = Query([])):
    influx_client=InfluxDBClient3(host=request.app.state.influx_db_url, token=request.app.state.influx_token, database="my_db")
    print('start_time',start_time,'options', options)
    # 1. 动态生成 140 个列名的列表：['temp0', 'temp1', ..., 'temp139']
    
    step = 1 if layer == -1 else 4
    start_index = 0 if layer == -1 else layer
    
    full_len= 140
    partial_len= int(140/step)
    temps_arr = [f"temp{i}" for i in range(start_index, full_len, step)]
    
    str_temp_sum = " + ".join(temps_arr)
    str_temps_arr=",".join(temps_arr)

    min_temp_clause= f"ROUND(MIN(LEAST({str_temps_arr}))/10.0,1) AS min_temp"
    max_temp_clause =f"ROUND(MAX(GREATEST({str_temps_arr}))/10.0,1) AS max_temp"
    avg_temp_clause= f"ROUND(AVG(({str_temp_sum}) / {partial_len})/10.0, 1) AS avg_temp"
            
    clauses=[]
    
    humid_cols = [f"humid{i}" for i in range(start_index, full_len, step)]
    str_humid_sum = " + ".join(humid_cols)
    str_humid_cols=",".join(humid_cols)
    min_humid_clause= f"ROUND(MIN(LEAST({str_humid_cols}))/10.0,1) AS min_humid"
    max_humid_clause =f"ROUND(MAX(GREATEST({str_humid_cols}))/10.0,1) AS max_humid"
    avg_humid_clause= f"ROUND(AVG(({str_humid_sum}) / {partial_len})/10.0, 1) AS avg_humid"

    if 'min' in options:
        clauses.append(min_temp_clause)
        clauses.append(min_humid_clause)

    if 'avg' in options:
        clauses.append(avg_temp_clause)
        clauses.append(avg_humid_clause)

    if 'max' in options:
        clauses.append(max_temp_clause)
        clauses.append(max_humid_clause)

    clauses_str= ", ".join(clauses)
    start = to_utctime(start_time)
    end = to_utctime(end_time)

    print(f'sql to execute {clauses_str}')
# -- 1. InfluxDB v3 核心函数：将时间戳按 1 小时(INTERVAL '1 HOUR')对齐，作为前端 X 轴时间
    query = f"""
        SELECT 
            {clauses_str},
            DATE_BIN(INTERVAL '10 minutes', a.time, TIMESTAMP '1970-01-01 00:00:00') chart_time 
        FROM plc_temp_data a left join plc_humid_data b 
            on DATE_BIN(INTERVAL '10 minutes', a.time, TIMESTAMP '1970-01-01 00:00:00')=DATE_BIN(INTERVAL '10 minutes', b.time, TIMESTAMP '1970-01-01 00:00:00') 
        where 
            a.time between '{start}' AND '{end}' and a.temp0 is not null
        group by chart_time 
        order by chart_time ASC
        """

    # 3. 执行查询并转换数据
    try:
        # language="sql" 显式指定使用 SQL引擎
        # print('to exectue',query)
        table = influx_client.query(query=query, language="sql")

        # 4. 将 PyArrow Table 转换为 Pandas DataFrame
        if table.num_rows == 0:
            return pd.DataFrame()
        # 将 PyArrow Table 转换为 Pandas DataFrame 以便后续分析
        df = table.to_pandas()
        print('found data\n',df)
        # print(f"查询到 {len(df)} 条数据")
        df['time'] = pd.to_datetime(df['chart_time']) + timedelta(hours=8)
        df['time'] = df['time'].dt.strftime('%y-%m-%d %H:%M')
        # df['avg_temp'] = (df['avg_temp']/10).round(1)
        # df['max_temp'] = (df['max_temp']/10).round(1)
        # df['avg_humid'] = (df['avg_humid']/10).round(1)
        
        # df['max_humid'] = (df['max_humid']/10).round(1)
        
        # 5. 核心：只筛选前端需要的 4 列
        # final_df = df[['time', 'avg', 'min', 'max']]
        # 某个时间点可能没有数据，需要将NaN转为None ,前端js可以识别null
        df = df.replace({np.nan: None})
        # print('final df', final_df)

        # 6. 一键转为 Python 列表字典结构 (对应 JSON 中的 [{...}, {...}])
        # orient='records' 是关键，它会自动处理 Pandas 中的 NaN 值为 Python 的 None (即 JSON 的 null)
        json_structure = df.to_dict(orient='records')
        # print('json_structure',json_structure)
        # print('df.head: ',df.head())
        return json_structure
    except Exception as e:
        print(f"查询失败: {e}")
    finally:
        influx_client.close()


# 显示平均功率，平均功耗
@router.get("/api/power-trend")
def get_power_history(request: Request,start_time: str,end_time: str, interval: str):
    print(f"'start_time',{start_time},interval: {interval}")
    influx_client=InfluxDBClient3(host=request.app.state.influx_db_url, token=request.app.state.influx_token, database="my_db")

    start = to_utctime(start_time)
    end = to_utctime(end_time)
    # interval='5 minutes'
# -- 1. InfluxDB v3 核心函数：将时间戳按 1 小时(INTERVAL '1 HOUR')对齐，作为前端 X 轴时间
    query = f"""
        SELECT 
            DATE_BIN(INTERVAL {interval}, time) AS chart_time, 
            ROUND(avg(power3),2) as avg_power,
            ROUND(MAX(power4) - LAG(MAX(power4), 1) OVER (ORDER BY DATE_BIN(INTERVAL {interval}, time)),2) AS engery_consumption 
        FROM plc_power_data
        where 
            time between '{start}' AND '{end}'
        GROUP BY DATE_BIN(INTERVAL {interval}, time)
        order by chart_time ASC
        """

    # 3. 执行查询并转换数据
    try:
        # language="sql" 显式指定使用 SQL引擎
        # print('to exectue',query)
        table = influx_client.query(query=query, language="sql")

        # 4. 将 PyArrow Table 转换为 Pandas DataFrame
        if table.num_rows == 0:
            return pd.DataFrame()
        # 将 PyArrow Table 转换为 Pandas DataFrame 以便后续分析
        df = table.to_pandas()
        print('found data\n',df)
        # print(f"查询到 {len(df)} 条数据")
        df['time'] = pd.to_datetime(df['chart_time']) + timedelta(hours=8)
        if interval.endswith('day'):
            df['time'] = df['time'].dt.strftime('%Y-%m-%d')
        elif interval.endswith('month'):
            df['time'] = df['time'].dt.strftime('%Y-%m')
        # final_df = df[['time', 'avg_temp', 'avg_humid']]
        # 某个时间点可能没有数据，需要将NaN转为None ,前端js可以识别null

        df = df.replace({np.nan: None})
        # print('final df', final_df)

        # 6. 一键转为 Python 列表字典结构 (对应 JSON 中的 [{...}, {...}])
        # orient='records' 是关键，它会自动处理 Pandas 中的 NaN 值为 Python 的 None (即 JSON 的 null)
        json_structure = df.to_dict(orient='records')
        # print('json_structure',json_structure)
        # print('df.head: ',df.head())
        return json_structure
    except Exception as e:
        print(f"查询失败: {e}")
    finally:
        influx_client.close()


# 控制接口
@router.post("/api/dev/control")
async def control_window(request: Request, data: dict):
    action_type = data.get('action_type')
    dev_id=data.get('dev_id')
    print(f'准备写入设备id {dev_id} , action_type: {action_type}')
    try:
        house_index = int(data.get('house_code')) -1
        plc_client=request.app.state.plc_conns[house_index]
        if dev_id:
            dev_info = dev_id.split('-')
            await request.app.state.write_single_reg(plc_client,int(dev_info[1]), action_type)
            print(f'写入PLC成功，设备id {dev_id}，动作 {action_type}')
        else:
            # batch devices
            category_type = data.get('category_type')
            await request.app.state(batch_dev_address[category_type], action_type)
            print(f'写入PLC全控设备{category_type}成功')
    except Exception as e:
            print(f"/api/dev/control 写入PLC异常: {e}")
    return {"success": True}


# 启动的action值，默认为1，都是开窗或启动# normal finish or cancelled
@router.post("/api/venti/adhoc/start")
async def venti_adhoc_start(request: Request, data: dict):
    # init job status before any actions
    print('here in adhoc start')
    try:
        venti_task_id=0
        flag=False
        house_index = int(data.get('house_code')) -1
        task_data={
            'house_code': data.get('house_code'), 
            'mode_name': None,  
            'mode_id': -1, 
            'status_code': 0,
            'status_text': '运行中',
            'create_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        venti_task_id = await persist_venti_task(task_data)
        task_data={}
        print(f'已新增记录 venti_task_id: {venti_task_id}')
        # init job cancel flag to false at job start
        request.app.state.is_job_cancelled[house_index] =False
        flag = await run_job(request, data)
        print(f'run_job flag : {flag}')
        if flag==0:
            task_data['status_code'] = 1
            task_data['status_text'] = '正常结束'
            print(f"已保持{data.get('duration')}分钟，准备复位")
        else:
            task_data['status_code'] = 4
            task_data['status_text'] = '被取消'
    except Exception as e:
        task_data['status_code'] = 5
        task_data['status_text'] = '异常中止'
    finally:
        task_data['update_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await stop_job(request, data)
        print(f'执行关闭命令完毕，等待45s待设备完全关闭')
        await asyncio.sleep(45)
        await update_venti_task(venti_task_id, task_data)
        # request.app.state.is_job_cancelled[house_index]= False


# 0: completed normally, 1: cancelled, 2: timeout, 3: terminated abnormally
async def run_job(request: Request, data: dict):
    try:
        devices = data.get('devices')
        duration= data.get('duration')
        house_code=data.get('house_code')
        action_obj= convert_dev_addr(devices, house_code, 1)
        print(f'start action obj: {action_obj}')
        # await execute_commands(request, action_obj, house_code)
        print(f'执行开启命令完毕，先等待45s待设备完全开启')
        await asyncio.sleep(45)
        
        elapsed=0
        house_index = int(house_code) -1
        # sleep minor amount of time
        while True:
            if elapsed < duration:
                print(f'计时，累计睡眠：{elapsed}')
                await asyncio.sleep(5)
                elapsed += 5
            else:
                print(f'已达到运行时长限制：{duration}')
                return 0
            if request.app.state.is_job_cancelled[house_index]:
                print(f"仓房{data.get('house_code')}作业被中止")
                # todo: update job record status as terminated
                return 1
    except asyncio.CancelledError:
        print('run_job() cancelled')
    except Exception as e:
        print(f'run_job异常:{e}')
        raise e
        

# restore devices
async def stop_job(request: Request, data: dict):
    devices = data.get('devices')
    action_obj = convert_dev_addr(devices,data.get('house_code'), 0)
    print(f'action_obj: {action_obj}')
    try:
        # await execute_commands(request, action_obj, data.get('house_code'))
        print(f'executed stop job commands')
        # todo: update job status centrally
    except Exception as e:
        print(f'stop job run in error: {e}')
        raise e

async def persist_venti_task(task_data: dict):
    # 1. 使用 Pydantic 进行第一轮严格的数据校验和清洗
    try:
        validated_data = VentiTaskCreate(**task_data)
    except Exception as e:
        print(f"❌ 报警数据格式校验失败: {e}")
        return

    # 2. 数据库会话上下文管 理
    async with AsyncSessionLocal() as session:
        try:
            print('in AsyncSessionLocal: ',AsyncSessionLocal)
            # 3. 将校验通过的数据转化为 SQLAlche0my 的模型实例
            # model_dump() 会把 Pydantic 对象变回 Python 字典（老版本 Pydantic 请用 .dict()）
            db_venti_task = VentiTask(**validated_data.model_dump())
            print(f'db_venti_task: {db_venti_task}')
            # 4. 执行插入并提交
            session.add(db_venti_task)
            await session.commit()
            print(f"💾 venti task已成功持久化到MySQL，自增 ID: {db_venti_task.id}")
            return db_venti_task.id
        except Exception as e:
            await session.rollback()
            print(f"❌ venti task入库失败，已自动回滚: {e}")



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
        print(f"❌ 更新数据格式校验失败: {e}")
        return False

    # 2. 数据库会话上下文管理
    async with AsyncSessionLocal() as session:
        try:
            print(f'in AsyncSessionLocal: {AsyncSessionLocal}')
            
            # 3. 🚀 关键步骤：先去数据库里查出这条已经存在的数据
            result = await session.execute(select(VentiTask).where(VentiTask.id == task_id))
            db_venti_task = result.scalars().first()
            
            if not db_venti_task:
                print(f"⚠️ 未找到 ID 为 {task_id} 的通风作业，无法执行更新")
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
            print(f"💾 venti task [ID: {task_id}] 已成功更新到 MySQL")
            return True
            
        except Exception as e:
            await session.rollback()
            print(f"❌ venti task 更新失败，已自动回滚: {e}")
            return False

async def get_running_venti_tasks(house_code) -> List[VentiTaskResponse]:
    async with AsyncSessionLocal() as session:
        try:
            # 1. 构建查询语句：SELECT * FROM ventilation_jobs WHERE status_code = 5
            # 如果想按时间倒序排列，可以加上 .order_by(VentiTask.create_time.desc())
            stmt = select(VentiTask).where(VentiTask.status_code.in_ ([-1, 0]), VentiTask.house_code == house_code)
            # 2. 异步执行查询
            result = await session.execute(stmt)
            # 3. 提取所有的 ORM 对象模型
            db_tasks = result.scalars().all()
            # 4. 利用 Pydantic 将 ORM 对象列表批量转换为响应模型列表
            
            # model_validate 配合列表推导式非常优雅且安全
            return [VentiTaskResponse.model_validate(task) for task in db_tasks]
            # return db_tasks
            
        except Exception as e:
            print(f"❌ 查询任务列表失败: {e}")
            return []

@router.get("/api/venti/jobs/{house_code}")
async def venti_jobs(house_code:str):
    running_jobs =await get_running_venti_tasks(house_code)
    print(f'running jobs {running_jobs}')
    return running_jobs
    
# 智能作业
#  任务状态： 等待触发（-1），运行中(0)，结束(1，正常完成 2，等待触发超时，3，等待结束超时， 4，cancelled  5，异常中止)
@router.post("/api/venti/sched/start")
async def venti_sched_start(request: Request, data: dict):
    try:
        house_index = int(data.get('house_code')) -1
        request.app.state.is_job_cancelled[house_index] =False
        # 检查开始条件
        print('开始智能作业')
        is_timeout=False
        ret=False
        
        #todo: create a task record with status 等待触发
        task_data={
            'mode_name': data.get('mode_name'), 
            'status_code': -1 ,
            'status_text': '等待触发',
            'create_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        venti_task_id=await persist_venti_task(task_data)
        task_data={}
        check_start_condition_task= asyncio.create_task(check_condition(request, data, 0,  None))
        ret = await asyncio.wait_for(check_start_condition_task, settings.sched_max_wait)
        print(f"ret {ret}")
        if ret==1:
            print("等待中被人为中止，作业结束")
            task_data['status_code'] = 4
            task_data['status_text'] = '被取消'
        # 条件满足，开始执行job
    except asyncio.TimeoutError:
        print(f"【等待触发超时错误】: 任务等待触发超过了设定的 {settings.sched_max_wait} 分钟限制，已被强制终止！")
            # todo: update record status as waiting timeout
        task_data['status_code'] = 2
        task_data['status_text'] = '等待触发超时'
        ret=2
    finally:
        if ret:
            await stop_job(request, data)
            print(f"reset is_job_cancelled for house-{house_index}")
            request.app.state.is_job_cancelled[house_index]=False
            task_data['update_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await update_venti_task(venti_task_id, task_data)
            return
        
    # todo: 需要开启设备
    # 检查结束条件
    try:
        #todo: create a task record with status running
        print('检查结束条件')
        task_run_job= asyncio.create_task(run_job(request, data))
        check_end_condition_task =asyncio.create_task(check_condition(request, data, 1, task_run_job))

        task_data['status_code'] = 0
        task_data['status_text'] = '运行中'
        task_data['update_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await update_venti_task(venti_task_id, task_data)
        results = await asyncio.gather(task_run_job, check_end_condition_task, return_exceptions=True)
        if results[1]==0:
            #todo: create a task record with status completed
            task_data['status_code'] = 1
            task_data['status_text'] = '正常结束'
        elif results[1]==1:
            #todo: create a task record with status cancelled
            task_data['status_code'] = 4
            task_data['status_text'] = '被取消'
        elif results[1]==2:
            # timeout
            print(f"【Job执行超时错误】: 作业运行超过了设定的 {data.get('duration')} 分钟限制，已被强制终止！")
            task_data['status_code'] = 3
            task_data['status_text'] =  '等待结束超时'
        else:
            #todo: create a task record with status exception
            task_data['status_code'] = 5
            task_data['status_text'] = '异常中止'
    except asyncio.TimeoutError:
        is_timeout=True
        print(f"【Job执行超时错误】: 作业运行超过了设定的 {data.get('duration')} 分钟限制，已被强制终止！")
        # todo: update record status as running timeout
    except Exception as e:
        #todo: create a task record with status exception
        print(f'Schedule job异常:{e}')
    finally:
        await stop_job(request, data)
        task_data['update_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await update_venti_task(venti_task_id, task_data)
        request.app.state.is_job_cancelled[house_index]=False
                


#  0: normal finish, 1: timed out
# async def check(task, duration):
#     elapsed=0
#     while True:
#         num_int = random.randint(1, 100)
#         print(f'……………………………………………………………… num in check: {num_int}')
#         elapsed +=3
#         if elapsed < duration:
#             await asyncio.sleep(3)
#         else:
#             task.cancel()
#             return 1
#         if num_int == 34:
#             task.cancel()
#             return 0
        
# 0: ConditionUpperSilo,#   1: ConditionAccumulatedHeat,#   2: ConditionWholeSilo,
# flag 0: start condition, 1: end condition
# 0: completed normally, 1: cancelled, 2: timeout, 3: terminated abnormally
async def check_condition(request, data, flag, task_run_job):
    house_index = int(data.get('house_code')) -1
    elapsed=0
    if data.get('mode_id')==0:
        # start_cond_1=max_internan_humid < data.get('end_condition').get('maxMoisture')
        # start_cond_2=surface_avg - ext_temp < data.get('end_condition').get('minTotalTempDiff')
        # surface_avg=None
        while True:

            sum=0
            for i in range(0, 140, 4):
                sum += request.app.state.global_display_temp_cache[house_index][i]
            surface_avg= round(sum/35,1)
            ext_temp=request.app.state.external_temp[house_index]
            temp_diff=data.get('start_condition').get('minTotalTempDiff')
            max_internan_humid= round(max(request.app.state.global_humid_cache[house_index])/10,1)

            print(f"当前仓内最大湿度{max(request.app.state.global_humid_cache[house_index])}，\
                  表层平均温度：{surface_avg}， 仓外温度{request.app.state.external_temp[house_index]}, 睡眠30s \
                  diff: {surface_avg - request.app.state.external_temp[house_index]}\
                  start_maxMoisture {data.get('start_condition').get('maxMoisture')}， \
                  start_minTotalTempDiff {data.get('start_condition').get('minTotalTempDiff')}，\
                  end maxMoisture {data.get('end_condition').get('maxMoisture')}， \
                  end minTotalTempDiff {data.get('end_condition').get('minTotalTempDiff')}"
                  )
            print(f'flag: {flag}, elsapsed {elapsed}')
            elapsed += 5
            if flag==0:
                if elapsed < settings.sched_max_wait:
                    await asyncio.sleep(5)
                else:
                    print(f"等待开始条件超时，cancel run_job")
                    # task_run_job.cancel()
                    return 2
                if max_internan_humid >= data.get('start_condition').get('maxMoisture')  \
                    and  surface_avg - ext_temp >= data.get('start_condition').get('minTotalTempDiff'):
                    print(f"满足开始条件")
                    return 0
            else:
                print(f"condtion 1：  {max_internan_humid < data.get('end_condition').get('maxMoisture')} \
                      condtion 2： {surface_avg - ext_temp < data.get('end_condition').get('minTotalTempDiff')}")
                
                if max_internan_humid < data.get('end_condition').get('maxMoisture')  \
                    and  surface_avg - ext_temp < data.get('end_condition').get('minTotalTempDiff'):
                    print('满足结束条件,等待10s后中止')
                    await asyncio.sleep(10)
                    task_run_job.cancel()
                    print('task_run_job cancelled')
                    return 0
                if elapsed < data.get('duration'):
                    print('未满足结束条件，继续睡眠5s')
                    await asyncio.sleep(5)
                else:
                    print(f"等待结束条件超时，cancel run_job")
                    task_run_job.cancel()
                    return 2
            if request.app.state.is_job_cancelled[house_index]:
                print('收到中止信号，停止等待结束条件')
                task_run_job.cancel()
                return 1
            
@router.post("/api/venti/job/stop")
async def venti_adhoc_stop(request: Request, data: dict):
    # todo # if running jobs：
    tasks= await get_running_venti_tasks(data.get('house_code'))
    print(f'running tasks: {tasks}')
    if not tasks:
        print('当前无运行中的作业')
        # raise Exception('当前无运行中的作业')
        return
    
        # update is_job_cancelled[house_index]
        # sleep 10 secs
        # restore is_cancelled if db status is not running        
    house_index = int(data.get('house_code')) -1
    request.app.state.is_job_cancelled[house_index] =True
    print(f"house-{data.get('house_code')} 作业停止信号已发出")
    

async def execute_commands(request, action_obj, house_code):
    house_index = int(house_code) -1
    plc_client = request.app.state.plc_conns[house_index]
    for key, value in action_obj.items():
        await request.app.state.write_single_reg(plc_client, int(key), value)


# async def stop_adhoc(request, action_obj, house_code):
#     house_index = int(house_code) -1
#     plc_client = request.app.state.plc_conns[house_index]
#     for key, value in action_obj.items():
#         await request.app.state.write_single_reg(plc_client, int(key), value)
   

#  flag 1: start job, 0: stop job
#  convert the address from ui to the json of register address and value
def convert_dev_addr(devices, house_code, flag):
    # {
    # 'windows': [1, 4], 'dampers': [], 'exhaustFans': [], 'airConditioners': [], 
    # 'blowers': {'1': None, '2': 1, '3': None, '4': None, '5': None, '6': None, '7': 1, '8': None}
    # }
    silo_addrs= load_silo_addrs(house_code)
    # print('devices: ',devices)
    # print('silo in convert_dev_addr:', silo_addrs)
    blowers = devices['blowers']
    blower_offset= silo_addrs['blowers'][0]
    action_val=1
    if not flag:
        action_val=3
    filtered_blowers = {int(key) + blower_offset - 1: action_val for key, value in blowers.items() if value is not None}
    # print(f'filtered_blowers {filtered_blowers}')
    filtered_dict={}
    # devices.pop("blowers", None) 
    # print(f'left devices {devices}')

    for key, value in devices.items():
        # print(f"键: {key} -> 值: {value}")
        if key=='blowers':
            continue
        addrs=devices[key]
        offset=silo_addrs[key][0]
        if flag:
            action_val=1
        elif key=='exhaustFans':
            action_val=3
        else:
            action_val=2
        filtered_dict =filtered_dict| {num + offset - 1: action_val for num in addrs}
    merged_dict = filtered_blowers | filtered_dict
    return merged_dict
            

def load_silo_addrs(house_code):
    # config_data=load_config()
    # config_data=settings.granaries
    
    # granaries = config_data.get('granaries', []) 
    granaries=settings.granaries
    house_index = int(house_code) -1
    
    # for silo in granaries:
    #     if (int)(silo['code'])==house_code:
    #         return silo['devices_addr']
    return granaries[house_index]['devices_addr']


# 报警确认
@router.post("/api/alarm/ack")
async def ack_alarm(request: Request, data: dict):
    try:
        alarm_key=data.get('alarm_key')
        print(' in ack ',alarm_key)
        request.app.state.active_alarms[alarm_key]['ack']=True
        request.app.state.active_alarms[alarm_key]['ack_time']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f'更新alarm ack成功')
        return {"success": True}
    except Exception as e:
        print(f"更新/api/alarm/ack异常: {e}")
