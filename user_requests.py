from datetime import timedelta

from fastapi import APIRouter, Request,WebSocket
import statistics
import asyncio 
from influxdb_client_3 import InfluxDBClient3
import numpy as np
import pandas as pd

from date_util import to_utctime

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
            avg_temp=round(statistics.mean(websocket.app.state.global_display_temp_cache),1)
            avg_humid=round(statistics.mean(websocket.app.state.global_humid_cache)/10,1)
            await websocket.send_json([avg_temp,avg_humid])
            # send to vue every 2 sec
            await asyncio.sleep(2)
    except Exception as e:
        print(f"客户端/ws/live断开连接: {e}")


@router.websocket("/ws/dev-state")
async def websocket_endpoint(websocket: WebSocket):
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
def get_history_data(request: Request,start_time: str,end_time: str):
    influx_client=InfluxDBClient3(host=request.app.state.influx_db_url, token=request.app.state.influx_token, database="my_db")
    print('start_time',start_time)
    # 1. 动态生成 140 个列名的列表：['temp0', 'temp1', ..., 'temp139']
    temp_cols = [f"temp{i}" for i in range(140)]
    avg_temp_sum = " + ".join(temp_cols)
    humid_cols = [f"humid{i}" for i in range(140)]
    avg_humid_sum = " + ".join(humid_cols)

    start = to_utctime(start_time)
    end = to_utctime(end_time)
# -- 1. InfluxDB v3 核心函数：将时间戳按 1 小时(INTERVAL '1 HOUR')对齐，作为前端 X 轴时间
    query = f"""
        SELECT 
            ROUND(AVG(({avg_temp_sum}) / 140.0), 1) AS avg_temp,
            ROUND(AVG(({avg_humid_sum}) / 140.0), 1) AS avg_humid,
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
        df['avg_temp'] = (df['avg_temp']/10).round(1)
        # df['min'] = (df['min_temp']/10).round(1)
        # df['max'] = (df['max_temp']/10).round(1)
        df['avg_humid'] = (df['avg_humid']/10).round(1)
        
        # 5. 核心：只筛选前端需要的 4 列
        # final_df = df[['time', 'avg', 'min', 'max']]
        final_df = df[['time', 'avg_temp', 'avg_humid']]
        # 某个时间点可能没有数据，需要将NaN转为None ,前端js可以识别null
        final_df = final_df.replace({np.nan: None})
        # print('final df', final_df)

        # 6. 一键转为 Python 列表字典结构 (对应 JSON 中的 [{...}, {...}])
        # orient='records' 是关键，它会自动处理 Pandas 中的 NaN 值为 Python 的 None (即 JSON 的 null)
        json_structure = final_df.to_dict(orient='records')
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
    # 1. 动态生成 140 个列名的列表：['temp0', 'temp1', ..., 'temp139']
    # temp_cols = [f"temp{i}" for i in range(140)]
    # avg_temp_sum = " + ".join(temp_cols)
    # humid_cols = [f"humid{i}" for i in range(140)]
    # avg_humid_sum = " + ".join(humid_cols)

    start = to_utctime(start_time)
    end = to_utctime(end_time)
# -- 1. InfluxDB v3 核心函数：将时间戳按 1 小时(INTERVAL '1 HOUR')对齐，作为前端 X 轴时间
    query = f"""
        SELECT 
            DATE_BIN(INTERVAL '1 hour', time) AS chart_time, 
            MAX(power4) - LAG(MAX(power4), 1) OVER (ORDER BY DATE_BIN(INTERVAL '1 hour', time)) AS engery_consumption 
        FROM plc_power_data
        where 
            time between '{start}' AND '{end}'
        GROUP BY DATE_BIN(INTERVAL '1 hour', time)
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
        else:
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
