import argparse
import os

from dotenv import load_dotenv
import uvicorn
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from pymodbus.client import AsyncModbusTcpClient
from contextlib import asynccontextmanager
import httpx
from str_join_util import  build_influx_line_protocol
from datetime import datetime
from database import Base, engine
from user_requests import router as user_request_router
from gran_router import router as gran_router

# 设置日志级别为 DEBUG，并自定义格式
# logging.basicConfig(
#     level=logging.error,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )

# logging.info('这是一条基础信息日志')

# ==================== 1. 全局变量 ====================
# 全局共享的 PLC 最新数据缓存（所有手机都来这里拿数据，不直接轰炸 PLC）

plc_client = None

DATABASE_NAME='my_db'


# 1. 解析参数并加载环境（必须在最外层）
parser = argparse.ArgumentParser()
parser.add_argument('--env', choices=['dev', 'test'], default='dev')
args, _ = parser.parse_known_args()
load_dotenv(dotenv_path=f".env.{args.env}")

# dev_start_address={'win':1,'door':11,'fan':19,'exhaust':27,'ac':33}

plc_lock = asyncio.Lock()
window_state = {"status": "stopped"}


# 最多读取120个寄存器
async def partial_read(start_address, cnt):
    async with plc_lock:
        result = await plc_client.read_holding_registers(address=start_address, count=cnt, device_id=1)
    if not result.isError():
        # print(f"【采集成功】温度数据: {result.registers} | 时间: {datetime.now()}")
        return result.registers
    else:
        print("【采集温度数据失败】PLC 内部错误响应")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # 如果表不存在，则自动创建（生产环境建议使用 Alembic 迁移）
        await conn.run_sync(Base.metadata.create_all)

    print("connected to mysql")
    app.state.plc_ip= os.getenv("PLC_IP", "127.0.0.1")
    app.state.plc_port=os.getenv("PLC_PORT")

    app.state.influx_db_url=os.getenv("INFLUX_DB_URL")
    app.state.influx_token=os.getenv("INFLUX_TOKEN")
    app.state.global_plc_cache = []
    app.state.global_display_temp_cache=[]
    app.state.global_humid_cache=[]
    app.state.partial_read=partial_read
    app.state.write_single_reg=write_single_reg

    print("\n--- 📊 当前环境配置变量 ---")
    print(f"🔗 后端服务 IP (DB_URL): {app.state.influx_db_url}")

    # 全局初始化一次异步客户端
    global plc_client
    try:
        
        plc_client = AsyncModbusTcpClient(app.state.plc_ip, port=app.state.plc_port, 
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
        # await write_single_reg(0,2)
        # 手动自动切换
        # await write_single_reg(399,2)
        # print('已切换为远程和手动')

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
app.include_router(user_request_router, tags=["用户管理"])
app.include_router(gran_router, tags=["仓房管理"])


# 1. 解决跨域问题（允许 Vue 前端和手机端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 生产环境建议指定具体 IP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



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
    # global global_plc_cache, global_display_temp_cache, global_humid_cache
    while True:
        if not plc_client.connected:
            print("【连接断开，等待自动重连】")
            await asyncio.sleep(3)
            continue
        try:
            
            app.state.global_plc_cache=await partial_read(35,120)
            # print("第1分片读取成功")
            # print(f"【采集成功】温度数据: {global_plc_cache[0]} | 时间: {datetime.now()}")
    
            # break
            app.state.global_plc_cache.extend(await partial_read(155,20))
            app.state.global_display_temp_cache = [round(x / 10, 1) for x in app.state.global_plc_cache]

            # 读取140个湿度数据
            app.state.global_humid_cache.extend(await partial_read(175,120))
            app.state.global_humid_cache.extend(await partial_read(195,20))
        except Exception as e:
            print(f"【采集异常】: {e}")
            
        # 这里控制采集频率：每 （1秒）高频采集一次
        await asyncio.sleep(1)


async def build_payload_str(data_cache, table, field_prefix):
    # 内存中不一定会立即有数据，需要判断
    try:
        if not data_cache:
            await asyncio.sleep(2)
            print('Error: data_cache is null, check next round')
            return ''
        plc_channels={}
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
    except Exception as e:
        raise Exception('##############build_payload_str 发生异常',e)


# todo: seperate as async minor tasks for temp and humid data storage
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
            try:
                # shouldn't be waiting here for 5mins. as it would cause long waiting
                # await asyncio.sleep(300)
                influx_data_line = await build_payload_str(app.state.global_plc_cache,'plc_temp_data','temp')
                if not influx_data_line:
                    continue
                await send_to_influx(influx_data_line)
                print('【温度数据存储成功】')
                # print('一次性退出')
                # break
                
                influx_data_line = await build_payload_str(app.state.global_humid_cache,'plc_humid_data','humid')
                if not influx_data_line:
                    continue
                await send_to_influx(influx_data_line)
                print('【湿度数据存储成功】')
            except Exception as e:
                print('【ERROR：】存储数据发生异常',e)
            #  每隔5 min存储一次
            await asyncio.sleep(3000)
    except KeyboardInterrupt:
        print("\n程序已手动停止。")
        # 关闭连接，释放资源
        plc_client.close()

async def send_to_influx(payload_text: str):
    """
    底层的异步发送函数，向 InfluxDB 发送 HTTP POST 请求
    """
    headers = {
        "Authorization": f"Token {app.state.influx_token}",
        "Content-Type": "text/plain; charset=utf-8"
    }
    WRITE_URL = f"{app.state.influx_db_url}/api/v3/write_lp?db={DATABASE_NAME}&precision=ns"

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
            raise Exception(f"[异常] 异步发送过程中发生错误: {e}")\

async def write_single_reg(start_add: int, val:int):
    async with plc_lock:
        response = await plc_client.write_register(address=start_add, value=val, device_id=1, no_response_expected=False)
    if response.isError():
        print("写入异常")
    else:
        print("写入成功，当前寄存器值:", response)        


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

if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description="智慧粮仓系统启动脚本")
    

    # 核心：启动内置 Web 容器，监听 0.0.0.0 允许局域网（手机）访问
    uvicorn.run("plc_server:app", host="0.0.0.0", port=8000, reload=True)