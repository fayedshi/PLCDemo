import asyncio

from fastapi import APIRouter, Request, Query, WebSocket

from datetime import timedelta

from fastapi import APIRouter, Query, Request

from influxdb_client_3 import InfluxDBClient3
import numpy as np
import pandas as pd

from date_util import to_utctime

from fastapi import APIRouter, Query
from logger.demo_logger import logger

router = APIRouter()

@router.websocket("/ws/gas/{gran_code}")
async def websocket_endpoint(websocket: WebSocket, gran_code: str):
    house_index=None
    await websocket.accept()
    print(f"【后端提示】/ws/gas前端house-{gran_code}客户端已连接！")
    try:
        house_index = int(gran_code) - 1
        while True:
            await websocket.send_json(websocket.app.state.global_gas_cache[house_index])
            # send to vue every 2 sec
            await asyncio.sleep(5)
    except Exception as e:
        print(f"客户端/ws/gas断开连接house-{gran_code}: {e}")

        
@router.get("/api/gas/querygas")
def show_cords_temp(request: Request, input_time: str, house_code: str):
    logger.info(f'input_time: {input_time}')
    influx_client=InfluxDBClient3(host=request.app.state.influx_db_url, token=request.app.state.influx_token, database="my_db")
    
    # input_time = obj.get('input_time')
    # start_time = f"{input_time}:00Z"
    # dt_obj = datetime.fromisoformat(input_time)
    # new_dt_obj = dt_obj + timedelta(minutes=1)
    # end_time = new_dt_obj.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    gas_cols = [f"gas{i}" for i in range(69)]
    gas_all_cols = ", ".join(gas_cols)
    time_clause= f"'{input_time}'" if input_time else "NOW() - INTERVAL '1 day'"

    query = f"""
            SELECT {gas_all_cols},time FROM plc_gas_data 
            WHERE station_id= '{house_code}' and time >= {time_clause}
            order by time desc limit 1
            """
    try:
        logger.info(f'to exectue {query}')
        table = influx_client.query(query=query, language="sql")

        # 4. 将 PyArrow Table 转换为 Pandas DataFrame
        if table.num_rows == 0:
            return pd.DataFrame()
        # 将 PyArrow Table 转换为 Pandas DataFrame 以便后续分析
        df = table.to_pandas()
        logger.info(f'found data\n{df}')
        logger.info(f"查询到 {len(df)} 条数据")
        # logger.info('df.head: ',df.head())
        dict_obj= df.to_dict(orient="records")[0]
        return list(dict_obj.values())
    except Exception as e:
        logger.error(f"查询失败: {e}")
    finally:
        influx_client.close()
