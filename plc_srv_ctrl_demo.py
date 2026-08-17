import uvicorn
import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from pymodbus.client import AsyncModbusTcpClient
from contextlib import asynccontextmanager

# ==================== 1. 全局变量 ====================
# 全局共享的 PLC 最新数据缓存（所有手机都来这里拿数据，不直接轰炸 PLC）

plc_client = None
PLC_IP='192.168.0.20'
PLC_PORT=502
plc_lock = asyncio.Lock()
# window_state = {"status": "stopped"}
start_address_map={1:1,2:2}
win_states=[]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 全局初始化一次异步客户端
    global plc_client
    plc_client = AsyncModbusTcpClient(PLC_IP, port=PLC_PORT)
    print("【系统启动】正在尝试与 PLC 建立唯一的长连接...")
    await plc_client.connect()
    print("【lifespan】物理通道已建立")
    polling_job=asyncio.create_task(plc_polling_task())
        # 本地远程切换，
    await write_single_reg(0,2)
    # 手动自动切换
    await write_single_reg(399,2)
    print('已切换为远程和手动')

    yield
    polling_job.cancel()

    try:
        await polling_job
    except asyncio.CancelledError:# interupted exception
        pass
    
    # 关闭：断开 PLC 连接
    print("正在断开 PLC 连接...")
    plc_client.close()

app = FastAPI(lifespan=lifespan)

# 1. 解决跨域问题（允许 Vue 前端和手机端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 生产环境建议指定具体 IP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def plc_polling_task():
    """该任务在后台独立运行，有且仅有它一个人维持与 PLC 的长连接"""
    global win_states, global_display_temp_cache
    while True:
        try:
            # result=await partial_read(35,120)
            result=await read_win_regs(365,2)
            win_states = result
            # print(f"电动窗状态读取成功时间: {datetime.now()}")
          
        except Exception as e:
            print(f"【采集异常】: {e}")
            await plc_client.connect()
            print("与 PLC重连成功")
            
        # 这里控制采集频率：每 （1秒）高频采集一次
        await asyncio.sleep(1)

async def write_single_reg(start_add: int, val:int):
    async with plc_lock:
        response = await plc_client.write_register(address=start_add, value=val, device_id=1, no_response_expected=False)
    if response.isError():
        print("写入异常")
    else:
        print("写入成功，当前寄存器值:", response)        

async def write_multi_regs(start_add: int, vals:list[int]):
    async with plc_lock:
        response = await plc_client.write_registers(address=start_add, values=vals, device_id=1, no_response_expected=False)
    if response.isError():
        print("写入异常")
    else:
        print("写入成功，当前寄存器值:", response)     
        return response.registers   

async def read_win_regs(start_add: int, len: int):
    async with plc_lock:
        result = await plc_client.read_holding_registers(address=start_add,count=len, device_id=1)
    if not result.isError():
        print(f"读取电动窗状态: {result.registers},  时间：{datetime.now()}")
        return result.registers
    else:
        print("读取失败")


async def write_win_contrl(win_ids:list[int], action_code: int):
    # global client
    print('in write_win_contrl', win_ids)
    start_add= start_address_map[win_ids[0]]
    vals=[]
    for i in range(0,len(win_ids)):
        vals.append(action_code)
    print('vals ',vals, 'start_add ',start_add)
    await write_multi_regs(start_add, vals)    
    

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    # 1. 接受前端的连接请求
    await websocket.accept()
    print("【后端提示】发现新的前端客户端已连接！")
    try:
        while True:
            await websocket.send_json(win_states)
            # 4. 每隔 500 毫秒推送一次（可自由调整为 100ms）
            await asyncio.sleep(1)
    except Exception as e:
        print(f"【后端提示】客户端已断开连接原因: {e}")


# 控制接口
@app.post("/api/windows/control")
async def control_window(data: dict):
    # print('in control wind')
    win_ids=data.get('win_ids')
    action_code=data.get('action_code')
    print(f'win ids {win_ids}, action code {action_code}')
    # 💡 写操作：跟后台轮询抢占同一个 plc_lock 锁
    # async with plc_lock:
    await write_win_contrl(win_ids, action_code)
    print('写入PLC窗控成功，win ids ',win_ids)
    return {"success": True}

if __name__ == "__main__":
    # 核心：启动内置 Web 容器，监听 0.0.0.0 允许局域网（手机）访问
    uvicorn.run("plc_srv_ctrl_demo:app", host="0.0.0.0", port=8000, reload=True)
