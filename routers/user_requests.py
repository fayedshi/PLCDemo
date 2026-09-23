from datetime import timedelta

from fastapi import APIRouter, Query, Request,WebSocket
import statistics
import asyncio 
from config import settings
from config_loader import load_config
from influxdb_client_3 import InfluxDBClient3
import numpy as np
import pandas as pd

from date_util import to_utctime
from schemas import AlarmLogResponse
from services.alarm_service import AlarmService

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status



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
@router.websocket("/ws/dev-state")
async def websocket_dev_state_endpoint(websocket: WebSocket, house_code):
    # global dev_state_cache
    await websocket.accept()
    print("【后端提示】发现/ws/dev-state前端客户端已连接！")
    try:
        house_index = int(house_code) -1
        house_config= load_silo_addrs(house_code) 
        dev_start= house_config['devices_addr']['window-state'][0]
        plc_client=websocket.app.state.plc_conns[house_index]
        while True:
            read_plc_func=websocket.app.state.partial_read
            dev_state_cache = await read_plc_func(plc_client,dev_start,32)
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


# 启动的action值，默认为1，都是开窗或启动
@router.post("/api/venti/adhoc/start")
async def venti_adhoc_start(request: Request, data: dict):
    run_job(request, data)


async def run_job(request: Request, data: dict):
    try:
        devices = data.get('devices')
        duration= data.get('duration')
        house_code=data.get('house_code')
        action_obj= convert_dev_addr(devices, house_code, 1)
        print(f'start action obj: {action_obj}')
        await execute_commands(request, action_obj, house_code)
        
        print(f'执行命令完毕，继续保持{duration}分钟')
        elapsed=0
        house_index = int(house_code) -1
        # sleep minor amount of time
        while True:
            if elapsed < duration:
                await asyncio.sleep(5)
                elapsed += 5
            else:
                break
            if request.app.state.is_job_cancelled[house_index]:
                print(f"仓房{data.get('house_code')}作业被中止")
                # todo: update job record status as terminated
                return False
        # 准备复位
        print(f'已保持{duration}分钟，准备复位')

        # await stop_job(request, data)
        # action_obj= convert_dev_addr(devices,house_code, 0)
        # print(f'restore action obj: ,{action_obj}')
        # await execute_commands(request, action_obj, house_code)
        
    # except asyncio.TimeoutError:
    #     print(f"【超时错误】: 任务执行超过了设定的 {duration} 分钟限制，已被强制终止！")
    #     # print(f"任务是否被取消: {adhoc_job.cancelled()}")
    except Exception as e:
        print(f'run_job异常:{e}')
        raise e

# restore devices
async def stop_job(request: Request, data: dict):
    devices = data.get('devices')
    action_obj = convert_dev_addr(devices,data.get('house_code'), 0)
    print(f'action_obj: {action_obj}')
    try:
        await execute_commands(request, action_obj, data.get('house_code'))
        # todo: update job status centrally
    except Exception as e:
        print(e)
        raise e
    
# 智能作业
@router.post("/api/venti/sched/start")
async def venti_sched_start(request: Request, data: dict):
    try:
        is_timeout=False
        is_proceed=False
        #todo: create a task record with status 等待触发
        check_condition_task= asyncio.create_task(
            check_start_condition(request, data.get('mode'), data.get('start_condition'), data.get('end_condition'), data.get('house_code')))
        is_proceed = await asyncio.wait_for(check_condition_task, settings.sched_max_wait)
        if not is_proceed:
            print("等待中被人为中止，作业结束")
        # 条件满足，开始执行job
    except asyncio.TimeoutError:
        print(f"【等待触发超时错误】: 任务等待触发超过了设定的 {settings.sched_max_wait} 分钟限制，已被强制终止！")
        is_timeout=True
            # todo: update record status as waiting timeout
    finally:
        if (not is_proceed) or is_timeout:
            await stop_job(request, data)
            return

    try:     
        is_proceed= await asyncio.wait_for(run_job(request, data), data.get('duration'))
        # if not is_proceed:
        #     stop_job(request, data)
        # todo: update record status as completed 
    except asyncio.TimeoutError:
        is_timeout=True
        print(f"【Job执行超时错误】: 作业运行超过了设定的 {data.get('duration')} 分钟限制，已被强制终止！")
        # todo: update record status as running timeout
    except Exception as e:
        print(f'Schedule job异常:{e}')
    finally:
        if (not is_proceed) or is_timeout:
            await stop_job(request, data)
            return    

# 0: ConditionUpperSilo,#   1: ConditionAccumulatedHeat,#   2: ConditionWholeSilo,
async def check_start_condition(request, mode, start_cond, end_cond, house_code):
    house_index = int(house_code) -1
    if(mode==0):
        # surface_avg=None
        while True:
            sum=0
            for i in range(0, 140, 4):
                sum += request.app.state.global_display_temp_cache[house_index][i]
            surface_avg= round(sum/35,1)
            ext_temp=request.app.state.external_temp[house_index]
            temp_diff=start_cond.get('minTotalTempDiff')
            print(f"当前仓内最大湿度{max(request.app.state.global_humid_cache[house_index])}，\
                  表层平均温度：{surface_avg}， 仓外温度{request.app.state.external_temp[house_index]}, 睡眠30s \
                  diff: {surface_avg - request.app.state.external_temp[house_index]}\
                  maxMoisture {start_cond.get('maxMoisture')}， \
                  minTotalTempDiff {start_cond.get('minTotalTempDiff')}"
                  )

            if max(request.app.state.global_humid_cache[house_index]) >= start_cond.get('maxMoisture')  \
                and  surface_avg - ext_temp >= temp_diff:
                print('满足开启条件')
                return True
            if request.app.state.is_job_cancelled[house_index]:
                return False
            await asyncio.sleep(5)
        
            
@router.post("/api/venti/job/stop")
async def venti_adhoc_stop(request: Request, data: dict):
    # devices = data.get('devices')
    # # duration= data.get('duration')
    # action_obj= convert_dev_addr(devices,data.get('house_code'), 0)
    # print(action_obj)
    # try:
    #     # todo: 这里不会超时，remove timeout later
    #     # result = await asyncio.wait_for(adhoc_job, timeout=duration)
    #     # print(f'正常结束，继续保持{duration}分钟')
    #     # asyncio.sleep(duration)
    #     await asyncio.create_task(execute_commands(request, action_obj, data.get('house_code')))
    # except Exception as e:
    #     print(e)
    # stop_job(request, data)
    
    house_index = int(data.get('house_code')) -1
    request.app.state.is_job_cancelled[house_index] =True
    print(f"house-{data.get('house_code')} 作业停止信号已发出")

async def execute_commands(request, action_obj, house_code):
    house_index = int(house_code) -1
    plc_client = request.app.state.plc_conns[house_index]
    for key, value in action_obj.items():
        await request.app.state.write_single_reg(plc_client, int(key), value)


async def stop_adhoc(request, action_obj, house_code):
    house_index = int(house_code) -1
    plc_client = request.app.state.plc_conns[house_index]
    for key, value in action_obj.items():
        await request.app.state.write_single_reg(plc_client, int(key), value)
   

#  flag 1: start job, 0: stop job
#  convert the address from ui to the json of register address and value
def convert_dev_addr(devices, house_code, flag):
    # {
    # 'windows': [1, 4], 'dampers': [], 'exhaustFans': [], 'airConditioners': [], 
    # 'blowers': {'1': None, '2': 1, '3': None, '4': None, '5': None, '6': None, '7': 1, '8': None}
    # }
    silo_addrs= load_silo_addrs(house_code)
    print('devices: ',devices)
    print('silo in convert_dev_addr:', silo_addrs)
    blowers = devices['blowers']
    blower_offset= silo_addrs['blowers'][0]
    action_val=1
    if not flag:
        action_val=3
    filtered_blowers = {int(key) + blower_offset - 1: action_val for key, value in blowers.items() if value is not None}
    print(f'filtered_blowers {filtered_blowers}')
    filtered_dict={}
    # devices.pop("blowers", None) 
    print(f'left devices {devices}')

    for key, value in devices.items():
        print(f"键: {key} -> 值: {value}")
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
