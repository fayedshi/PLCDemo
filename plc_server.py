import uvicorn
import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
# from pymodbus_read import read_plc
# from pymodbus.client import ModbusTcpClient
# from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime
from pymodbus.client import AsyncModbusTcpClient
from contextlib import asynccontextmanager
import random

# ==================== 1. 全局变量 ====================
# 全局共享的 PLC 最新数据缓存（所有手机都来这里拿数据，不直接轰炸 PLC）
global_plc_cache = [] 
plc_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 全局初始化一次异步客户端
    global plc_client
    plc_client = AsyncModbusTcpClient('192.168.0.20', port=502)
    print("【系统启动】正在尝试与 PLC 建立唯一的长连接...")
    await plc_client.connect()
    print("【lifespan】物理通道已建立")
    polling_job=asyncio.create_task(plc_polling_task())
    
    yield
    
    # 关闭：断开 PLC 连接
    print("正在断开 PLC 连接...")
    polling_job.cancel()

    try:
        await polling_job
    except asyncio.CancelledError:# interupted exception
        plc_client.close()
        print("采集任务已停止，与PLC的连接已释放完毕")    

app = FastAPI(lifespan=lifespan)

# app = FastAPI()
# 1. 解决跨域问题（允许 Vue 前端和手机端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 生产环境建议指定具体 IP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ==================== PLC 异步采集任务 ====================
async def plc_polling_task():
    """该任务在后台独立运行，有且仅有它一个人维持与 PLC 的长连接"""
    global global_plc_cache
    while True:
        try:
            #使用 await 进行异步读取，读取期间绝对不卡死 FastAPI 服务器
            result = await plc_client.read_holding_registers(address=35, count=10, device_id=1) # 新版本 pymodbus 用 slave 代替 device_id
            if not result.isError():
                global_plc_cache = result.registers
                print(f"【采集成功】数据: {global_plc_cache} | 时间: {datetime.now()}")
            else:
                print("【采集失败】PLC 内部错误响应")            
        except Exception as e:
            print(f"【采集异常】: {e}")
            await plc_client.connect()
            print("与 PLC重连成功")
            
        # 💡 这里控制采集频率：每 100 毫秒（0.1秒）高频采集一次
        await asyncio.sleep(1)


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
            plc_data = global_plc_cache
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
    result = query_api.query(org="your_org", query=flux_query)
    
    history_list = []
    for table in result:
        for record in table.records:
            history_list.append({
                "time": record.get_time(),
                "temperature": record.values.get("temperature"),
                "pressure": record.values.get("pressure"),
                "total_count": record.values.get("total_count")
            })
    return {"status": "success", "data": history_list}

if __name__ == "__main__":
    # 核心：启动内置 Web 容器，监听 0.0.0.0 允许局域网（手机）访问
    uvicorn.run("plc_server:app", host="0.0.0.0", port=8000, reload=True)
