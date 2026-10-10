import asyncio
from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect
from logger.demo_logger import logger
from config import settings
import requests
from requests.auth import HTTPDigestAuth
import xml.etree.ElementTree as ET

router = APIRouter()

NVR_USER = "admin"
NVR_PASS = "LC1314pp"
NVR_IP = "192.168.0.241"

# 全局状态管理字典
channel_connections = {}  # { "live_101": [ws1, ws2] }
ffmpeg_tasks = {}         # { "live_101": asyncio.Task } （存放异步读流任务对象）

def get_rtsp_url(channel: str) -> str:
    return f"rtsp://{NVR_USER}:{NVR_PASS}@{NVR_IP}:554/Streaming/Channels/{channel}"

async def start_async_ffmpeg_engine(channel_key: str, rtsp_url: str):
    """
    ⭐ 核心重构：利用 asyncio 原生异步子进程代替多线程
    纯单线程异步驱动，利用操作系统的异步 I/O，绝不产生多线程死锁
    """
    if channel_key in ffmpeg_tasks:
        return

    cmd = [
        'ffmpeg', '-rtsp_transport', 'tcp', '-i', rtsp_url,
        '-f', 'mpegts', '-codec:v', 'mpeg1video',
        '-tune', 'zerolatency', '-g', '5', '-flush_packets', '1',
        '-s', '640x360', '-bf', '0', '-r', '20', '-an', '-'
    ]

    # 1. 异步启动 FFmpeg 子进程
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL
    )
    print(f"▶️ 异步 FFmpeg 进程启动，绑定 Key: {channel_key}")

    async def async_stream_pump():
        """非阻塞异步数据泵：完全在单线程事件循环中通过 await 异步抽水"""
        try:
            while process.returncode is None:
                # ⭐ 纯异步非阻塞读取 32KB 数据，绝不锁死主线程
                data = await process.stdout.read(32768)
                if not data:
                    break
                
                # 如果当前通道已经没人看了，主动切断
                if channel_key not in channel_connections or not channel_connections[channel_key]:
                    break

                # 异步广播给当前订阅该通道的所有网页客户端
                if channel_key in channel_connections:
                    tasks = [ws.send_bytes(data) for ws in channel_connections[channel_key]]
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"❌ 通道 {channel_key} 异步分发发生异常: {e}")
        finally:
            # 2. 完美的善后关闭闭环
            try:
                process.terminate()
                await process.wait()
            except:
                pass
            ffmpeg_tasks.pop(channel_key, None)
            print(f"⏹️ 纯异步进程已彻底安全释放，Key: {channel_key}")

    # 3. 将这个读流分发循环挂载为当前事件循环的后台异步 Task
    ffmpeg_tasks[channel_key] = asyncio.create_task(async_stream_pump())

# 🌐 路由 1：处理实时视频流
@router.websocket("/stream/live/{channel}")
async def websocket_live(websocket: WebSocket, channel: str):
    await websocket.accept()
    channel_key = f"live_{channel}"
    
    if channel_key not in channel_connections:
        channel_connections[channel_key] = []
    channel_connections[channel_key].append(websocket)
    
    rtsp_url = get_rtsp_url(channel)
    # 直接触发纯异步引擎
    await start_async_ffmpeg_engine(channel_key, rtsp_url)
    
    try:
        while True:
            await websocket.receive_text()  # 维持心跳
    except WebSocketDisconnect:
        channel_connections[channel_key].remove(websocket)

# 🌐 路由 2：处理历史录像回放流
@router.websocket("/stream/playback/{channel}")
async def websocket_playback(websocket: WebSocket, channel: str, start_time: str):
    await websocket.accept()
    channel_key = f"pb_{channel}_{hash(websocket)}"
    
    if channel_key not in channel_connections:
        channel_connections[channel_key] = []
    channel_connections[channel_key].append(websocket)
    
    # 2026-10-07T18:00:00Z ->starttime=20261007t180000z
    # 规整海康回放时间格式 2026/10/8 020500
    # hk_time = start_time.replace("-", "").replace(":", "").lower()
    playback_url = f"rtsp://{NVR_USER}:{NVR_PASS}@{NVR_IP}:554/Streaming/tracks/{channel}?starttime={start_time}"
    print(f"🎬 异步唤醒回放流: {playback_url}")
    
    await start_async_ffmpeg_engine(channel_key, playback_url)
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        channel_connections[channel_key].remove(websocket)
        if channel_key in channel_connections:
            channel_connections.pop(channel_key, None)


@router.get("/api/nvr/channels")
async def get_channel_list():
    nvr_config_list= settings.raw_config['NVR_LIST']
    print(nvr_config_list)
    nvr_channels=[]
    for nvr_config in nvr_config_list:
        channel_config=load_nvr(nvr_config)
        nvr_channels.append(channel_config)
    logger.info(f'all channels: {nvr_channels}')
    return nvr_channels


def load_nvr(config):
    nvr_ip = config['IP']
    NVR_USER = config["USER"]
    NVR_PASS = config['PASSWORD']
    # NVR_PORT= config['PORT']

    # NVR_IP = "192.168.1.64"  # 替换为你的NVR IP
    # username = "admin"
    # password = "YOUR_PASSWORD"
    url = f"http://{nvr_ip}/ISAPI/ContentMgmt/InputProxy/channels"
    print(url)
    try:
        # 海康ISAPI必须使用 HTTP 摘要认证 (Digest Auth)
        response = requests.get(url, auth=HTTPDigestAuth(NVR_USER, NVR_PASS), timeout=5)
        # print(f'response: {response.text}')
        if response.status_code == 200:
            # 解析返回的 XML 数据
            root = ET.fromstring(response.text)
            
            # 海康的命名空间标签头
            ns = {'hk': 'http://www.hikvision.com/ver20/XMLSchema'}
            
            print(f"{'通道ID':<10}{'通道名称':<20}")
            print("-" * 30)
            channel_json={}
            # 遍历所有输入通道
            for channel in root.findall('.//hk:InputProxyChannel', ns):
                channel_id = channel.find('hk:id', ns).text
                channel_name = channel.find('hk:name', ns).text
                channel_json[channel_id]=channel_name
                print(f"{channel_id:<10}{channel_name:<20}")
            return channel_json
        else:
            print(f"请求失败，状态码: {response.status_code}，请检查密码或NVR服务是否开启。")
    except Exception as e:
        print(f"连接 NVR 发生异常: {e}")