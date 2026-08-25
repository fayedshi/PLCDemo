import uvicorn
import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client_3 import InfluxDBClient3
from datetime import datetime
from pymodbus.client import AsyncModbusTcpClient
from contextlib import asynccontextmanager
import httpx
from str_join_util import  build_influx_line_protocol
import pandas as pd
from datetime import datetime, timedelta
from date_util import to_utctime
import logging.config

# 设置日志级别为 DEBUG，并自定义格式
# logging.basicConfig(
#     level=logging.error,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )

# logging.info('这是一条基础信息日志')

# ==================== 1. 全局变量 ====================
# 全局共享的 PLC 最新数据缓存（所有手机都来这里拿数据，不直接轰炸 PLC）
global_plc_cache = [] 
global_humid_cache=[]
global_display_temp_cache=[]
dev_state_cache=[]
plc_client = None
PLC_IP='192.168.0.20'
PLC_PORT=503
INFLUX_DB_URL='http://localhost:8181'
INFLUX_TOKEN='apiv3_ntcKjOE7rToG5Z9tcxJ9XQj1_8Bm-ANFgIECpNtyhPeBuSJstAglB_pF1awNFt9oUcCZL4Og9kwd3wnMDG29gQ'
DATABASE_NAME='my_db'

# dev_start_address={'win':1,'door':11,'fan':19,'exhaust':27,'ac':33}
batch_dev_address={'window':31,'door':32}
plc_lock = asyncio.Lock()
window_state = {"status": "stopped"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 全局初始化一次异步客户端
    global plc_client
    try:
        plc_client = AsyncModbusTcpClient(PLC_IP, port=PLC_PORT, 
            reconnect_delay=1.0,
            reconnect_delay_max=120 
        )
        print("【系统启动】正在尝试与 PLC 建立唯一的长连接...")
        await plc_client.connect()
        print("【lifespan】物理通道已建立")

        polling_job=asyncio.create_task(plc_polling_task())
        # 不等，先直接异步执行下面代码了，所以global_plc_cache为空
        storage_job=asyncio.create_task(influx_storage_task())
        # 本地远程切换，
        await write_single_reg(0,2)
        # 手动自动切换
        await write_single_reg(399,2)
        print('已切换为远程和手动')

        yield

    finally:
        # 关闭：断开 PLC 连接
        print("正在断开 PLC 连接...")
        polling_job.cancel()
        storage_job.cancel()

        try:
            await asyncio.gather(polling_job,storage_job)
        except asyncio.CancelledError:# interupted exception
            pass
        plc_client.close()
        print("###采集任务已停止，与PLC的连接已释放完毕")

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
    global global_plc_cache, global_display_temp_cache, global_humid_cache
    while True:
        if not plc_client.connected:
            print("【连接断开，等待自动重连】")
            await asyncio.sleep(3)
            continue
        try:
            global_plc_cache=await partial_read(35,120)
            # print("第1分片读取成功")
            # print(f"【采集成功】温度数据: {global_plc_cache[0]} | 时间: {datetime.now()}")
    
            # break
            global_plc_cache.extend(await partial_read(155,20))
            global_display_temp_cache = [round(x / 10, 1) for x in global_plc_cache]

            # 读取140个湿度数据
            global_humid_cache.extend(await partial_read(175,120))
            global_humid_cache.extend(await partial_read(195,20))
        except Exception as e:
            print(f"【采集异常】: {e}")
            
        # 这里控制采集频率：每 （1秒）高频采集一次
        await asyncio.sleep(1)


async def build_payload_str(data_cache, table, field_prefix):
    # try:
        # 内存中不一定会立即有数据，需要判断
        if not data_cache:
            await asyncio.sleep(2)
        if not data_cache:
            print('Error: data_cache is null, to return')
            return ''
        plc_channels={}
        # while True:
        for i in range(0,140):
            plc_channels[f"{field_prefix}{i}"] = data_cache[i]
            # print(global_plc_cache[i])
        device_tags = {
            "plc_type": "s7-smart200",
            "station_id": "line_01"
        }

        # 动态生成 140 个字段的行协议数据
        influx_data_line = await build_influx_line_protocol(
            measurement=table, 
            tags = device_tags, 
            fields=plc_channels
        )
        
        print(f'拼接后的字符串： {influx_data_line}')
        return influx_data_line
            #
    # except KeyboardInterrupt:
    #     print("存储异常")
    #     # 关闭连接，释放资源
    #     plc_client.close()

async def influx_storage_task():
    # ==================== 3. 核心循环采集 ====================
    try:
        print("正在启动上位机采集与存储服务...")
        # print(global_plc_cache)
        
        # plc_channels={}
        # if not global_plc_cache:
        #     await asyncio.sleep(2)
        # if not global_plc_cache:
        #     print('Error global_plc_cache is null, to return')
        #     return
        
        while True:
            await asyncio.sleep(300)
            influx_data_line = await build_payload_str(global_plc_cache,'plc_temp_data','temp')
            if not influx_data_line:
                continue
            await send_to_influx(influx_data_line)
            print('【温度数据存储成功】')
            # print('一次性退出')
            # break
            
            influx_data_line = await build_payload_str(global_humid_cache,'plc_humid_data','humid')
            if not influx_data_line:
                continue
            await send_to_influx(influx_data_line)
            print('【湿度数据存储成功】')
            #  每隔5 min存储一次
            # await asyncio.sleep(3000)
            
            
        #     for i in range(0,140):
        #         plc_channels[f"temp{i}"] = global_plc_cache[i]
        #         # print(global_plc_cache[i])
        #     device_tags = {
        #         "plc_type": "s7-smart200",
        #         "station_id": "line_01"
        #     }

        #     # 动态生成 140 个字段的行协议数据
        #     influx_data_line = build_influx_line_protocol(
        #         measurement="plc_temp_data", 
        #         tags = device_tags, 
        #         fields=plc_channels
        #     )
        #     if not influx_data_line:
        #         continue
        #     # print(f'拼接后的字符串： {influx_data_line}')
            
        #     # 每隔1 min存储一次
        #     await asyncio.sleep(300)
        #     await send_to_influx(influx_data_line)

    except KeyboardInterrupt:
        print("\n程序已手动停止。")
        # 关闭连接，释放资源
        plc_client.close()

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
                print(f"[成功] 成功异步写入数据块，大小: {len(payload_text.splitlines())} 行，时间: {datetime.now()}")
            else:
                print(f"[错误] 写入失败，状态码: {response.status_code}, 原因: {response.text}")
        except Exception as e:
            print(f"[异常] 异步发送过程中发生错误: {e}")\

async def write_single_reg(start_add: int, val:int):
    async with plc_lock:
        response = await plc_client.write_register(address=start_add, value=val, device_id=1, no_response_expected=False)
    if response.isError():
        print("写入异常")
    else:
        print("写入成功，当前寄存器值:", response)        


# 控制接口
@app.post("/api/dev/control")
async def control_window(data: dict):
    action_type = data.get('action_type')
    dev_id=data.get('dev_id')
    print(f'准备写入设备id {dev_id} , action_type: {action_type}')
    try:
        if dev_id:
            dev_info = dev_id.split('-')
            await write_single_reg(int(dev_info[1]), action_type)
            print(f'写入PLC成功，设备id {dev_id}，动作 {action_type}')
        else:
            # batch devices
            category_type = data.get('category_type')
            await write_single_reg(batch_dev_address[category_type], action_type)
            print(f'写入PLC全控设备{category_type}成功')
    except Exception as e:
            print(f"/api/dev/control 写入PLC异常: {e}")
    return {"success": True}


# 3. WebSocket 接口（用于向手机和本地 Vue 实时推送 Modbus 数据）
@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("【后端提示】/ws/live前端客户端已连接！")
    try:
        while True:
            plc_data = global_display_temp_cache
            # print('in live ',global_plc_cache)
            await websocket.send_json(plc_data)
            # send to vue every 2 sec
            await asyncio.sleep(2)
    except Exception as e:
        print(f"客户端/ws/live断开连接: {e}")


@app.websocket("/ws/dev-state")
async def websocket_endpoint(websocket: WebSocket):
    global dev_state_cache
    await websocket.accept()
    print("【后端提示】发现/ws/dev-state前端客户端已连接！")
    try:
        while True:
            dev_state_cache = await partial_read(365,32)
            await websocket.send_json(dev_state_cache)
            # send to vue every 2 sec
            await asyncio.sleep(1)
    except Exception as e:
        print(f"ws/dev-state客户端断开连接 : {e}")


# 4. Web 接口：对外远程管理 ====================
# 远程查询接口：手机端向 InfluxDB 索要过去 1 小时的历史趋势图表
# @app.get("/api/history")
# def get_history_data(range_str: str = "-1h"):
#     db_client = InfluxDBClient(url="http://localhost:8086", token="YOUR_TOKEN", org="YOUR_ORG")
#     query_api = db_client.query_api()
#     # 编写 InfluxDB 的 Flux 查询语句
#     flux_query = f'''
#     from(bucket: "your_bucket")
#       |> range(start: {range_str})
#       |> filter(fn: (r) => r["_measurement"] == "factory_line_01")
#       |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
#     '''
#     result = query_api.query(query=flux_query)
    
#     history_list = []
#     return {"status": "success", "data": history_list}

@app.get("/api/tempbytime")
def show_cords_temp(input_time: str):
    print('input_time', input_time)
    # db_client = InfluxDBClient(url="http://localhost:8086", token="YOUR_TOKEN", org="YOUR_ORG")
    influx_client=InfluxDBClient3(host=INFLUX_DB_URL, token=INFLUX_TOKEN,database="my_db")

    # 2. 定义 SQL 查询
    # 注意：时间字符串需符合 RFC3339格式，并用单引号包裹
    
    # input_time = obj.get('input_time')
    # start_time = f"{input_time}:00Z"
    # dt_obj = datetime.fromisoformat(input_time)
    # new_dt_obj = dt_obj + timedelta(minutes=1)
    # end_time = new_dt_obj.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    temp_cols = [f"temp{i}" for i in range(140)]
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
    influx_client=InfluxDBClient3(host=INFLUX_DB_URL, token=INFLUX_TOKEN,database="my_db")

    # 2. 定义 SQL 查询
    # 注意：时间字符串需符合 RFC3339格式，并用单引号包裹
    print('start_time',start_time)
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

        # query humid data


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

if __name__ == "__main__":
    # 核心：启动内置 Web 容器，监听 0.0.0.0 允许局域网（手机）访问
    uvicorn.run("plc_server:app", host="0.0.0.0", port=8000, reload=True)
