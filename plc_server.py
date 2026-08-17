import uvicorn
import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client_3 import InfluxDBClient3, Point, WritePrecision
# from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime
from pymodbus.client import AsyncModbusTcpClient
from contextlib import asynccontextmanager
import httpx
import time
from str_join_util import  build_influx_line_protocol
import pandas as pd
from datetime import datetime, timedelta, timezone
from date_util import to_utctime, to_localtime

# ==================== 1. 全局变量 ====================
# 全局共享的 PLC 最新数据缓存（所有手机都来这里拿数据，不直接轰炸 PLC）
global_plc_cache = [] 
global_display_temp_cache=[]
plc_client = None
influx_client=None
PLC_IP='192.168.0.20'
PLC_PORT=502
INFLUX_DB_URL='http://192.168.0.100:8181'
INFLUX_TOKEN='apiv3_gfbZbQ6OB0qk3dWCCp7EFmUzNj23GX20aAZN_TSILbu0X1y18kncU8Uf3JcHtFfYPD9b887iNP37QmLJ-RIwCg'
DATABASE_NAME='my_db'
plc_lock = asyncio.Lock()
window_state = {"status": "stopped"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 全局初始化一次异步客户端
    global plc_client, influx_client
    plc_client = AsyncModbusTcpClient(PLC_IP, port=PLC_PORT)
    print("【系统启动】正在尝试与 PLC 建立唯一的长连接...")
    await plc_client.connect()
    print("【lifespan】物理通道已建立")

    polling_job=asyncio.create_task(plc_polling_task())
    # 不等，先直接异步执行下面代码了，所以global_plc_cache为空
    # await asyncio.sleep(5)
    # print('sleeping 5 sec')
    print('break',global_plc_cache)
    storage_job=asyncio.create_task(influx_storage_task())
    
    yield
    
    # 关闭：断开 PLC 连接
    print("正在断开 PLC 连接...")
    polling_job.cancel()
    storage_job.cancel()

    try:
        await polling_job
    except asyncio.CancelledError:# interupted exception
        pass

    try:
        await storage_job
    except asyncio.CancelledError:# interupted exception
        pass

    plc_client.close()
    print("###采集任务已停止，与PLC的连接已释放完毕")
    print("###数据存储任务已停止")

app = FastAPI(lifespan=lifespan)

# 1. 解决跨域问题（允许 Vue 前端和手机端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 生产环境建议指定具体 IP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 最多读取120个寄存器
async def partial_read(start_address, cnt):
    async with plc_lock:
        result = await plc_client.read_holding_registers(address=start_address, count=cnt, device_id=1)
    if not result.isError():
        # print(f"【采集成功】温度数据: {result.registers} | 时间: {datetime.now()}")
        return result.registers
    else:
        print("【采集温度数据失败】PLC 内部错误响应")

import struct
def registers_to_float(reg_high, reg_low):
    """
    将西门子 PLC 的两个 16 位寄存器转换为 32 位浮点数
    :param reg_high: 第一个寄存器（地址较小的，高 16 位）
    :param reg_low: 第二个寄存器（地址较大的，低 16 位）
    """
    # 按照大端序格式将两个 16 位无符号整数(H)打包成 4 字节二进制数据
    raw_bytes = struct.pack(">HH", reg_high, reg_low)
    
    # 将这 4 字节数据按照大端序解包为 32 位浮点数(f)
    float_val = struct.unpack(">f", raw_bytes)[0]
    
    return round(float_val, 4)

# === 验证示例 ===
# 假设 PLC 内部真实的浮点数是 50.5
# 西门子 PLC 中读取出来的两个 16 位十进制整数分别为：16946 和 0
# reg1 = 16946
# reg2 = 0

# result = siemens_registers_to_float(reg1, reg2)
# print(f"解析西门子浮点数结果: {result}")  # 输出: 50.5


# ==================== PLC 异步采集任务 ====================
async def plc_polling_task():
    """该任务在后台独立运行，有且仅有它一个人维持与 PLC 的长连接"""
    global global_plc_cache, global_display_temp_cache
    while True:
        try:
            result=await partial_read(35,120)
            global_plc_cache += result
            # print("第1分片读取成功")
            # print(f"【采集成功】温度数据: {global_plc_cache[0]} | 时间: {datetime.now()}")
            # print("先中止，",global_plc_cache[1])
            # break
            global_plc_cache.extend(await partial_read(120,20))
            global_display_temp_cache = [round(x / 10, 1) for x in global_plc_cache]
            # print(f"【采集成功】温度数据: {global_plc_cache} | 时间: {datetime.now()}")
            # print("第2分片读取成功")
            # global_plc_cache.extend(await partial_read(240,120))
            # print("第3分片读取成功")
            # global_plc_cache.extend(await partial_read(360,120))
            # print("第4分片读取成功")
        except Exception as e:
            print(f"【采集异常】: {e}")
            await plc_client.connect()
            print("与 PLC重连成功")
            
        # 这里控制采集频率：每 （1秒）高频采集一次
        await asyncio.sleep(1)

async def influx_storage_task():
    # 激活写入 API (使用同步写入模式，适合入门调试)
    # write_api = influx_client.write_api(write_options=SYNCHRONOUS)

    # ==================== 3. 核心循环采集 ====================
    try:
        print("正在启动上位机采集与存储服务...")
        # print(global_plc_cache)
        # print("************************...")
        plc_channels={}
        if not global_plc_cache:
            await asyncio.sleep(2)
        if not global_plc_cache:
            print('Error global_plc_cache is null, to return')
            return

        while True:
            for i in range(0,140):
                plc_channels[f"temp{i}"] = global_plc_cache[i]
                # print(global_plc_cache[i])
            device_tags = {
                "plc_type": "s7-smart200",
                "station_id": "line_01"
            }

            # 动态生成 140 个字段的行协议数据
            influx_data_line = build_influx_line_protocol(
                measurement="plc_temp_data", 
                tags = device_tags, 
                fields=plc_channels
            )
            if not influx_data_line:
                continue
            # print(f'拼接后的字符串： {influx_data_line}')
            
            # 每隔1 min存储一次
            await send_to_influx(influx_data_line)
            await asyncio.sleep(3600)
            # break

    except KeyboardInterrupt:
        print("\n程序已手动停止。")
        # 关闭连接，释放资源
        plc_client.close()
        influx_client.close()

async def send_to_influx(payload_text: str):
    """
    底层的异步发送函数，向 InfluxDB 发送 HTTP POST 请求
    """
    headers = {
        "Authorization": f"Token {INFLUX_TOKEN}",
        "Content-Type": "text/plain; charset=utf-8"
    }
    WRITE_URL = f"{INFLUX_DB_URL}/api/v3/write_lp?db={DATABASE_NAME}&precision=ns"

    # 使用 httpx.AsyncClient 建立异步 HTTP 客户端
    async with httpx.AsyncClient() as client:
        try:
            # content 参数接收纯文本的行协议数据（多行用 \n 分割）
            response = await client.post(WRITE_URL, headers=headers, content=payload_text, timeout=10.0)
            
            # InfluxDB 3 写入成功时通常返回 204 No Content
            if response.status_code == 204:
                print(f"[成功] 成功异步写入数据块，大小: {len(payload_text.splitlines())} 行")
            else:
                print(f"[错误] 写入失败，状态码: {response.status_code}, 原因: {response.text}")
        except Exception as e:
            print(f"[异常] 异步发送过程中发生错误: {e}")\


# 2. 普通 HTTP 接口（用于手机或本地 Vue 控制设备）
@app.post("/api/control")
def control_device(command: dict):
    # 这里编写 Modbus TCP 写入逻辑
    print(f"收到控制指令: {command}")
    return {"status": "success", "msg": "指令已发送给 PLC"}


# 3. WebSocket 接口（用于向手机和本地 Vue 实时推送 Modbus 数据）
@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("【后端提示】发现新的前端客户端已连接！")
    try:
        while True:
            plc_data = global_display_temp_cache
            # print('in live ',global_plc_cache)
            await websocket.send_json(plc_data)
            # send to vue every 2 sec
            await asyncio.sleep(2)
    except Exception as e:
        print(f"客户端断开连接: {e}")


# 4. Web 接口：对外远程管理 ====================
# 远程查询接口：手机端向 InfluxDB 索要过去 1 小时的历史趋势图表
@app.get("/api/history")
def get_history_data(range_str: str = "-1h"):
    db_client = InfluxDBClient(url="http://localhost:8086", token="YOUR_TOKEN", org="YOUR_ORG")
    query_api = db_client.query_api()
    # 编写 InfluxDB 的 Flux 查询语句
    flux_query = f'''
    from(bucket: "your_bucket")
      |> range(start: {range_str})
      |> filter(fn: (r) => r["_measurement"] == "factory_line_01")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    result = query_api.query(query=flux_query)
    
    history_list = []
    return {"status": "success", "data": history_list}

@app.get("/api/tempbytime")
def get_history_data(input_time: str):
    # db_client = InfluxDBClient(url="http://localhost:8086", token="YOUR_TOKEN", org="YOUR_ORG")
    influx_client=InfluxDBClient3(host=INFLUX_DB_URL, token=INFLUX_TOKEN,database="my_db")

    # 2. 定义 SQL 查询
    # 注意：时间字符串需符合 RFC3339格式，并用单引号包裹
    print('input_time',input_time)
    # start_time = f"{input_time}:00Z"
    # dt_obj = datetime.fromisoformat(input_time)
    # new_dt_obj = dt_obj + timedelta(minutes=1)
    # end_time = new_dt_obj.strftime('%Y-%m-%dT%H:%M:%SZ')
    if not input_time:
        query = f"""
            SELECT * FROM plc_temp_data order by time desc limit 1
            """
    else:
        start_time=to_utctime(input_time)
        query = f"""
            SELECT *
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



@app.get("/api/temp-trend")
def get_history_data(start_time: str,end_time: str):
    # db_client = InfluxDBClient(url="http://localhost:8086", token="YOUR_TOKEN", org="YOUR_ORG")
    influx_client=InfluxDBClient3(host=INFLUX_DB_URL, token=INFLUX_TOKEN,database="my_db")

    # 2. 定义 SQL 查询
    # 注意：时间字符串需符合 RFC3339格式，并用单引号包裹
    print('input_time',start_time)
    # 1. 动态生成 140 个列名的列表：['temp0', 'temp1', ..., 'temp139']
    temp_cols = [f"temp{i}" for i in range(140)]
    avg_sum_part = " + ".join(temp_cols)
    min_max_params=", ".join(temp_cols)
    start = to_utctime(start_time)
    end = to_utctime(end_time)
# -- 1. InfluxDB v3 核心函数：将时间戳按 1 小时(INTERVAL '1 HOUR')对齐，作为前端 X 轴时间
    query = f"""
        
        SELECT 
        DATE_BIN(INTERVAL '10 minutes', time, TIMESTAMP '1970-01-01 00:00:00') AS chart_time,
        ROUND(AVG(({avg_sum_part}) / 140.0), 1) AS avg_temp,
      
        MIN(LEAST({min_max_params})) AS min_temp,
        MAX(GREATEST({min_max_params})) AS max_temp
    FROM 
        plc_temp_data
    WHERE 
        time >= '{start}' AND time <= '{end}' and temp0 is not null
    GROUP BY 
        chart_time
    ORDER BY 
        chart_time ASC;
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
        df['time']=pd.to_datetime(df['chart_time'])+timedelta(hours=8)
        df['time']=df['time'].dt.strftime('%y-%m-%d %H:%M')
        # 4. 对数据列进行四舍五入保留 1 位小数，并重命名为前端匹配的短字段名
        # df['avg_temp'] = pd.to_numeric(df['avg_temp'].round(1),errors='coerce')

        df['avg'] = (df['avg_temp']/10).round(1)
        df['min'] = (df['min_temp']/10).round(1)
        df['max'] = (df['max_temp']/10).round(1)
        print('after sql')
        # 5. 核心：只筛选前端需要的 4 列
        final_df = df[['time', 'avg', 'min', 'max']]
        # 6. 一键转为 Python 列表字典结构 (对应 JSON 中的 [{...}, {...}])
        # orient='records' 是关键，它会自动处理 Pandas 中的 NaN 值为 Python 的 None (即 JSON 的 null)
        json_structure = final_df.to_dict(orient='records')
        print(json_structure)
        # print('df.head: ',df.head())
        return json_structure
    except Exception as e:
        print(f"查询失败: {e}")
    finally:
        influx_client.close()

# 获取状态接口
@app.get("/api/window/status")
async def get_window_status():
    return window_state


# 控制接口
@app.post("/api/气调模块/window/control")
async def control_single_window(action_code: int):
    # action = payload.action
    # if action not in ACTION_MAP:
    #     raise HTTPException(status_code=400, detail="非法控制指令")

    control_value = ACTION_MAP[action]

    # 💡 写操作：跟后台轮询抢占同一个 plc_lock 锁
    async with plc_lock:
        # 独占物理连接，安全调用 write_register 写入数据
        await plc_client.write_register(address=1, value=action_code)
        
        # 写入成功后，同步更新内存缓存
        window_state["status"] = "opening" if action == "open" else ("closing" if action == "close" else "stopped")

    return {"success": True, "current_status": window_state["status"]}

if __name__ == "__main__":
    # 核心：启动内置 Web 容器，监听 0.0.0.0 允许局域网（手机）访问
    uvicorn.run("plc_server:app", host="0.0.0.0", port=8000, reload=True)
