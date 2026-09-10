from datetime import timedelta

from fastapi import APIRouter, Query, Request,WebSocket
import statistics
import asyncio 
from influxdb_client_3 import InfluxDBClient3
import numpy as np
import pandas as pd
from sqlalchemy import select

from database import AsyncSessionLocal
from date_util import to_utctime
import models
from schemas import AlarmLogResponse
from services.alarm_service import AlarmService

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel


router = APIRouter(tags=["用户模块"])
batch_dev_address={'window':31,'door':32}


# 3. WebSocket 接口（用于向手机和本地 Vue 实时推送 Modbus 数据）
@router.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    
    await websocket.accept()
    print("【后端提示】/ws/live前端客户端已连接！")
    try:
        while True:
            # plc_data = global_display_temp_cache
            # print('in live ',global_plc_cache)
            if not websocket.app.state.global_plc_cache:
                await asyncio.sleep(2)
                continue
            avg_temp=round(statistics.mean(websocket.app.state.global_display_temp_cache),1)
            avg_humid=round(statistics.mean(websocket.app.state.global_humid_cache)/10,1)
            # websocket.app.state.global_power_cache
            send_buffer=websocket.app.state.global_power_cache[:4]
            # data=[avg_temp,avg_humid]
            send_buffer.extend([avg_temp,avg_humid])
            # print(data)
            await websocket.send_json(send_buffer)
            # send to vue every 2 sec
            await asyncio.sleep(2)
    except Exception as e:
        print(f"客户端/ws/live断开连接: {e}")


# 4. WebSocket 接口：供前端实时连接
@router.websocket("/ws/alarms")
async def websocket_alarms_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(f"客户端/ws/alarms已连接:")
    # connected_clients.add(websocket)
    try:
        while True:
            # await websocket.receive_text() # 维持心跳
            # print(f'alarms: {websocket.app.state.active_alarms}')
            # 握手成功后，立刻把当前“正在发生”的报警推给前端，防止前端刷新页面后看板变空
            await websocket.send_json(
                websocket.app.state.active_alarms
            )
            await asyncio.sleep(10)
    except Exception as e:
        print(f"客户端/ws/alarms断开连接: {e}")

    # except WebSocketDisconnect:
        # connected_clients.remove(websocket)

# @router.get("/history", response_model=List[AlarmResponse])
# async def get_history_alarms(
#     house_id: Optional[int] = Query(None, description="按仓房ID筛选"),
#     severity: Optional[str] = Query(None, description="按严重程度筛选 (info/warning/critical)"),
#     start_time: Optional[datetime] = Query(None, description="开始时间 (ISO格式，如 2026-03-30T00:00:00)"),
#     end_time: Optional[datetime] = Query(None, description="结束时间"),
#     page: int = Query(1, ge=1, description="当前页码"),
#     size: int = Query(20, ge=1, le=100, description="每页条数，最大100")
# ):
#     """
#     获取历史报警记录（支持多条件筛选与高效分页）
#     """
#     # 🎯 开启异步会话（纯读取操作，无需使用 session.begin() 开启事务）
#     async with AsyncSessionLocal() as session:
#         try:
#             # 1. 构建基础查询语句（按时间倒序排列，最新报警在前）
#             query = select(AlarmLog).order_by(desc(AlarmLog.created_at))
            
#             # 2. 动态拼装筛选条件
#             if house_id is not None:
#                 query = query.where(AlarmLog.house_id == house_id)
                
#             if severity is not None:
#                 query = query.where(AlarmLog.severity == severity)
                
#             if start_time is not None:
#                 query = query.where(AlarmLog.created_at >= start_time)
                
#             if end_time is not None:
#                 query = query.where(AlarmLog.created_at <= end_time)
            
#             # 3. 执行分页切片 (Pagination)
#             offset = (page - 1) * size
#             query = query.offset(offset).limit(size)
            
#             # 4. 执行异步查询
#             result = await session.execute(query)
#             alarms = result.scalars().all()
            
#             return alarms
            
#         except Exception as e:
#             # 发生不可预知的数据库异常时，记录日志并安全向前端抛出
#             print(f"查询历史报警数据库失败: {str(e)}")
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail="系统内部数据库查询异常"
#             )

# 假设的导入路径
# from database import AsyncSessionLocal
# from services.alarm import AlarmService

# router = APIRouter(prefix="/api/alarms", tags=["历史报警"])

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
        print('alarms, ', alarms)
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


@router.websocket("/ws/dev-state")
async def websocket_dev_state_endpoint(websocket: WebSocket):
    # global dev_state_cache
    await websocket.accept()
    print("【后端提示】发现/ws/dev-state前端客户端已连接！")
    try:
        while True:
            read_plc_func=websocket.app.state.partial_read
            dev_state_cache = await read_plc_func(365,32)
            await websocket.send_json(dev_state_cache)
            # send to vue every 2 sec
            await asyncio.sleep(1)
    except Exception as e:
        print(f"ws/dev-state客户端断开连接 : {e}")



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
        if dev_id:
            dev_info = dev_id.split('-')
            await request.app.state.write_single_reg(int(dev_info[1]), action_type)
            print(f'写入PLC成功，设备id {dev_id}，动作 {action_type}')
        else:
            # batch devices
            category_type = data.get('category_type')
            await request.app.state(batch_dev_address[category_type], action_type)
            print(f'写入PLC全控设备{category_type}成功')
    except Exception as e:
            print(f"/api/dev/control 写入PLC异常: {e}")
    return {"success": True}
