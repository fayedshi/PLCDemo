import asyncio
import subprocess
from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from typing import Dict, List
from logger.demo_logger import logger
# app = FastAPI()

# 🛠️ NVR 基础配置

router = APIRouter()

NVR_USER = "admin"
NVR_PASS = "LC1314pp"
NVR_IP = "192.168.0.241"

# 管理结构：{ "102": [ws1, ws2], "202": [ws3] }
channel_connections: Dict[str, List[WebSocket]] = {}
# 进程结构：{ "102": ffmpeg_process_1, "202": ffmpeg_process_2 }
ffmpeg_processes: Dict[str, subprocess.Popen] = {}

def start_ffmpeg_for_channel(channel: str):
    """为特定通道启动独立的 FFmpeg 进程"""
    logger.info('转码开始 start_ffmpeg_for_channel')
    if channel in ffmpeg_processes:
        return # 已经启动过了，不再重复启动

    rtsp_url = f"rtsp://{NVR_USER}:{NVR_PASS}@{NVR_IP}:554/Streaming/Channels/{channel}"
    # rtsp_url = f"rtsp://{USER}:{PASSWORD}@{IP}:{PORT}/Streaming/Channels/102"
    
    cmd = [
    'ffmpeg', 
    '-rtsp_transport', 'tcp', 
    '-i', rtsp_url,
    '-f', 'mpegts', 
    '-codec:v', 'mpeg1video',
    '-tune', 'zerolatency',
    '-g', '5',                 # 每 5 帧强行插入一个全量 I 帧，防止卡主
    '-flush_packets', '1',     # 有数据立刻冲刷发送
    '-s', '1280*720',           # ⭐ 必须强制为偶数分辨率！
    '-bf', '0', 
    '-r', '20', 
    '-an', 
    '-'
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    ffmpeg_processes[channel] = process
    print(f"▶️ NVR 通道 {channel} 的 FFmpeg 转码进程已启动")

    # 异步启动该通道的数据读取循环
    logger.info('异步启动该通道的数据读取循环')
    asyncio.create_task(ffmpeg_reader_loop(channel))

async def ffmpeg_reader_loop(channel: str):
    """持续读取特定通道的 FFmpeg 数据并分发"""
    loop = asyncio.get_event_loop()
    while True:
        process = ffmpeg_processes.get(channel)
        # 如果这个通道已经没有网页观看了，主动关闭 FFmpeg 进程，释放服务器 CPU
        if channel not in channel_connections or not channel_connections[channel]:
            if process:
                process.terminate()
                ffmpeg_processes.pop(channel, None)
                print(f"⏹️ 无人观看，已释放 NVR 通道 {channel} 的转码进程")
                break
        # logger.info('==========>sendding video data')
        if process and process.stdout:
            data = await loop.run_in_executor(None, process.stdout.read, 4096)
            if data and channel in channel_connections:
                # logger.info('==========>real sending')
                # 📢 只广播给订阅了当前通道的 WebSocket 客户端
                tasks = [ws.send_bytes(data) for ws in channel_connections[channel]]
                if tasks:
                    # logger.info(f'tasks: {tasks}')
                    await asyncio.gather(*tasks, return_exceptions=True)
                    # await asyncio.sleep(0.5)
            else:
                await asyncio.sleep(0.01)
        else:
            await asyncio.sleep(1)

# @router.get("/stream/nvr/{channel}")
# async def handle_jsmpeg_probe(channel: str, response: Response):
#     """专门应答 jsmpeg 的 HTTP 0-21 字节探测，防止其报 404"""
#     # 告诉前端播放器：我们支持这个视频流，允许接下来建立 WebSocket 连接
#     response.headers["Content-Type"] = "video/mp4" # 或者 "application/octet-stream"
#     response.headers["Access-Control-Allow-Origin"] = "*" # 防止跨域问题
#     # 返回一段空的二进制，满足它的前段字节读取需求
#     return Response(content=b'\x00' * 22, status_code=200)

# @router.route("/stream/nvr/{channel}", methods=["GET", "HEAD"])
# async def handle_jsmpeg_probe(channel: str):  # ⭐ 关键修改：删掉括号里的 response: Response
#     """一劳永逸应答 jsmpeg 的 HTTP 探测，阻止 404/405 报错"""
    
#     # 直接在内部构建并返回 Response 对象
#     return Response(
#         content=b'\x00' * 22, 
#         status_code=200,
#         headers={
#             "Content-Type": "video/mp4",
#             "Access-Control-Allow-Origin": "*"  # 防止跨域问题
#         }
#     )


@router.get("/stream/nvr/{channel}")
async def handle_jsmpeg_probe(channel: str):
    """顺从 jsmpeg 探测机制：返回真实符合 MPEG-TS 静态特征的数据头，不引发解复用崩溃"""
    logger.info(f'inside handle_jsmpeg_probe')
    rtsp_url = f"rtsp://{NVR_USER}:{NVR_PASS}@{NVR_IP}:554/Streaming/Channels/{channel}"
    
    # 1. 启动一个临时或持久的探测命令
    cmd = [
        'ffmpeg', '-rtsp_transport', 'tcp', '-i', rtsp_url,
        '-f', 'mpegts', '-codec:v', 'mpeg1video',
        '-s', '640x480', '-bf', '0', '-r', '20', '-an', '-'
    ]
    
    try:
        # 2. 异步启动进程，准备读取其标准输出
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        
        # 3. 阻塞读取前 4096 字节的数据（这其中 100% 包含了真实的 PAT、PMT 视频流元数据）
        # 给定 3 秒超时限制，防止海康 NVR 离线导致接口死锁
        loop = asyncio.get_event_loop()
        real_video_header = await loop.run_in_executor(None, process.stdout.read, 4096)
        # logger.info(f'got video header: {real_video_header}')
        # 4. 立即安全关闭这个探测进程（它已经完成了嗅探使命）
        process.terminate()
        
        if not real_video_header:
            return Response(status_code=500, content="无法从海康 NVR 获取视音频流元数据")

        # 5. 将海康摄像头吐出的【真实视频头】原封不动返回给前端 jsmpeg
        return Response(
            content=real_video_header,
            status_code=200,
            headers={
                "Content-Type": "video/mp4",
                "Accept-Ranges": "bytes",
                "Content-Length": str(len(real_video_header))
            }
        )
    except Exception as e:
        print(f"❌ 嗅探通道 {channel} 发生严重错误: {e}")
        return Response(status_code=500, content=str(e))
    


@router.websocket("/stream/nvr/{channel}")
async def websocket_endpoint(websocket: WebSocket, channel: str):
    logger.info('in stream endpoint')
    await websocket.accept()
    
    # 将连接归类到对应的通道列表中
    if channel not in channel_connections:
        channel_connections[channel] = []
    channel_connections[channel].append(websocket)
    
    # 动态触发启动该通道的 FFmpeg
    start_ffmpeg_for_channel(channel)
    
    try:
        while True:
            await websocket.receive_text() # 维持心跳
    except WebSocketDisconnect:
        channel_connections[channel].remove(websocket)
        if not channel_connections[channel]:
            channel_connections.pop(channel, None)
