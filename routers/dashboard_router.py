
from fastapi import APIRouter, WebSocket
import statistics
import asyncio
from config import settings
from logger.demo_logger import logger

from fastapi import APIRouter

router = APIRouter()

granaries= settings.granaries

@router.get("/api/houses/codes")
async def get_house_codes():
    print(f'length of grannaries {len(granaries)}')
    house_code_list= [gran['code'] for gran in granaries]
    print(f'house_code_list: {house_code_list}')
    logger.info(f'house_code_list: {house_code_list}')
    return house_code_list

# 3. WebSocket 接口（用于向手机和本地 Vue 实时推送 Modbus 数据）
@router.websocket("/ws/live/{gran_code}")
async def websocket_endpoint(websocket: WebSocket, gran_code: str):
    house_index=None
    await websocket.accept()
    print(f"【后端提示】/ws/live前端house-{gran_code}客户端已连接！")
    try:
        house_index = int(gran_code) -1
        while True:
            # print('global_display_temp_cache in ws/live', websocket.app.state.global_power_cache[house_index])
            avg_temp=round(statistics.mean(websocket.app.state.global_display_temp_cache[house_index]),1)
            avg_humid=round(statistics.mean(websocket.app.state.global_humid_cache[house_index])/10,1)
            # websocket.app.state.global_power_cache
            send_buffer=websocket.app.state.global_power_cache[house_index][:4]
            # print(f'power: {websocket.app.state.global_power_cache[house_index]}')
            # data=[avg_temp,avg_humid]
            send_buffer.extend([avg_temp,avg_humid])
            
            await websocket.send_json(send_buffer)
            # send to vue every 2 sec
            await asyncio.sleep(300)
    except Exception as e:
        logger.info(f"客户端/ws/live断开连接house-{gran_code}: {e}")



