########################
# 4.Vue 3 + Python (FastAPI)实时通信最小demo
########################




# 第一步：编写 Python后端服务 (server.py)
import asyncio
import random
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# 允许跨域，保证本地 Vue 项目和手机端能够正常连接
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
            await asyncio.sleep(0.5)
            
    except Exception as e:
        print(f"【后端提示】客户端已断开连接原因: {e}")

if __name__ == "__main__":
    # 监听 0.0.0.0，不仅本地能访问，局域网内的手机输入电脑 IP 也能访问
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)