
from fastapi import APIRouter, Query, Request,WebSocket
import asyncio

from config_loader import load_config

from schemas import AlarmLogResponse
from services.alarm_service import AlarmService

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status

router = APIRouter()


# config_data=load_config()
# granaries = config_data.get('granaries', [])

# 4. WebSocket 接口：供前端实时连接
@router.websocket("/ws/alarms")
async def websocket_alarms_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(f"客户端/ws/alarms已连接:")
    # connected_clients.add(websocket)
    try:
        # 不需要分仓房，本来就是收集多个仓房
        # house_index = int(house_code) -1
        websocket.app.state.read_alarm_interval= 2
        # manual execute once to expose alarms
        # websocket.app.state.check_temp_alarm('TEMP_HIGH', gran['code'], index)
        while True:
            # await websocket.receive_text() # 维持心跳
            # print(f'alarms: {websocket.app.state.active_alarms}')
            # 握手成功后，立刻把当前“正在发生”的报警推给前端，防止前端刷新页面后看板变空
            await websocket.send_json(
                websocket.app.state.active_alarms
            )
            await asyncio.sleep(2)
    except Exception as e:
        print(f"客户端/ws/alarms断开连接: {e}")
    finally:
        websocket.app.state.read_alarm_interval= 5

    # except WebSocketDisconnect:
        # connected_clients.remove(websocket)

# --- API 接口定义 ---
@router.get("/api/alarms/history", response_model=AlarmLogResponse)
async def get_history_alarms(
    house_code: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    # 🎯 注入我们的 Service 层
    service: AlarmService = Depends(AlarmService)
):
    try:
        # 🚀 路由层变得极其干净，只负责调用 Service 并传递参数
        alarms, alarms_total = await service.get_history(
            house_code=house_code,
            severity=severity,
            start_time=start_time,
            end_time=end_time,
            page=page,
            size=size
            # page=page, size=size
        )
        # print('alarms, ', alarms)
        return {
            "historyTotal": alarms_total,
            "items": alarms
        }
    except Exception as e:
        print(f"Service 层执行异常: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统内部业务处理异常"
        )


# 报警确认
@router.post("/api/alarm/ack")
async def ack_alarm(request: Request, data: dict):
    try:
        alarm_key=data.get('alarm_key')
        print(' in ack ',alarm_key)
        request.app.state.active_alarms[alarm_key]['ack']=True
        request.app.state.active_alarms[alarm_key]['ack_time']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f'更新alarm ack成功')
        return {"success": True}
    except Exception as e:
        print(f"更新/api/alarm/ack异常: {e}")
