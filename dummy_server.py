########################
# 4.Vue 3 + Python (FastAPI)实时通信最小demo
########################

# 第一步：编写 Python后端服务 (server.py)
import asyncio
import random
from fastapi import FastAPI, WebSocket
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from fastapi import APIRouter, WebSocket
import statistics
import asyncio
from config import settings
from logger.demo_logger import logger

from fastapi import APIRouter


granaries= settings.granaries

app = FastAPI()

# 允许跨域，保证本地 Vue 项目和手机端能够正常连接
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.data_cache=[]
    # app.state.plc_port=os.getenv("PLC_PORT")
    
    try:
        print('创建read task')
        task_read_data=asyncio.create_task(read_temp())
        yield
    finally:
        print("正在中止所有task...")
        task_read_data.cancel()

        try:
            await task_read_data
        except asyncio.CancelledError:# interupted exception
            pass
        

app = FastAPI(lifespan=lifespan)

async def read_temp():
    while(True):
        try:
            mock_data = [round(random.uniform(20.0, 35.0), 1), # 模拟 20~35 度
                        round(random.uniform(4.0, 6.0), 2),      # 模拟 4~6 Mpa
                            # "status": "RUNNING"
                        ]
            print(f'mock_data: {mock_data}')
            # print(f'mock_data: {mock_data}')
            if mock_data[0] > 30:
                print(f"*****************PLC内部异常 in read_temp()，等待1分钟")
                await asyncio.sleep(3)
                continue
            app.state.data_cache =mock_data
        except Exception as e:
            print(f'############## read_temp发生异常: {e}, ')
        await asyncio.sleep(30)

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    # 1. 接受前端的连接请求
    await websocket.accept()
    print("【后端提示】发现新的前端客户端已连接！")
    
    try:
        while True:
            # 2. 模拟 PLC 数据产生（实际开发中这里改为读取内存缓存或硬件）
            mock_data = [
                 round(random.uniform(20.0, 35.0), 1), # 模拟 20~35 度
                 round(random.uniform(4.0, 6.0), 2),      # 模拟 4~6 Mpa
                # "status": "RUNNING"
            ]
            
            # 3. 发送 JSON 数据给前端 Vue
            await websocket.send_json(mock_data)
            
            # 4. 每隔 500 毫秒推送一次（可自由调整为 100ms）
            await asyncio.sleep(3)
            
    except Exception as e:
        print(f"【后端提示】客户端已断开连接原因: {e}")


@app.get("/api/houses/codes")
async def get_house_cnt():
    print(f'length of grannaries {len(granaries)}')
    house_code_list= [gran['code'] for gran in granaries]
    print(f'house_code_list: {house_code_list}')
    logger.info(f'house_code_list: {house_code_list}')
    return house_code_list


@app.get("/api/dev-address/{house_code}")
async def get_dev_addr_list(house_code):
    house_index = int(house_code) -1
    return settings.granaries[house_index]['devices_addr']



if __name__ == "__main__":
    # 监听 0.0.0.0，不仅本地能访问，局域网内的手机输入电脑 IP 也能访问
    uvicorn.run("dummy_server:app", host="0.0.0.0", port=8000, reload=True)