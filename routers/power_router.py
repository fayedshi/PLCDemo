from datetime import timedelta
from fastapi import APIRouter, Request
from influxdb_client_3 import InfluxDBClient3
import numpy as np
import pandas as pd

from date_util import to_utctime

from fastapi import APIRouter
from logger.demo_logger import logger


router = APIRouter(tags=["能耗监测模块"])
batch_dev_address={'window':31,'door':32}


# 显示平均功率，平均功耗
@router.get("/api/power-trend")
def get_power_history(request: Request,start_time: str,end_time: str, interval: str):
    logger.info(f"'start_time',{start_time},interval: {interval}")
    influx_client=InfluxDBClient3(host=request.app.state.influx_db_url, token=request.app.state.influx_token, database="my_db")

    start = to_utctime(start_time)
    end = to_utctime(end_time)
    # interval='5 minutes'
# -- 1. InfluxDB v3 核心函数：将时间戳按 1 小时(INTERVAL '1 HOUR')对齐，作为前端 X 轴时间
    query = f"""
        SELECT 
            DATE_BIN(INTERVAL {interval}, time) AS chart_time, 
            ROUND(avg(power3),2) as avg_power,
            ROUND(MAX(power4) - LAG(MAX(power4), 1) OVER (ORDER BY DATE_BIN(INTERVAL {interval}, time)),2) AS engery_consumption 
        FROM plc_power_data
        where 
            time between '{start}' AND '{end}'
        GROUP BY DATE_BIN(INTERVAL {interval}, time)
        order by chart_time ASC
        """

    # 3. 执行查询并转换数据
    try:
        # language="sql" 显式指定使用 SQL引擎
        # logger.info('to exectue',query)
        table = influx_client.query(query=query, language="sql")

        # 4. 将 PyArrow Table 转换为 Pandas DataFrame
        if table.num_rows == 0:
            return pd.DataFrame()
        # 将 PyArrow Table 转换为 Pandas DataFrame 以便后续分析
        df = table.to_pandas()
        logger.info(f'found data\n,{df}')
        # logger.info(f"查询到 {len(df)} 条数据")
        df['time'] = pd.to_datetime(df['chart_time']) + timedelta(hours=8)
        if interval.endswith('day'):
            df['time'] = df['time'].dt.strftime('%Y-%m-%d')
        elif interval.endswith('month'):
            df['time'] = df['time'].dt.strftime('%Y-%m')
        # final_df = df[['time', 'avg_temp', 'avg_humid']]
        # 某个时间点可能没有数据，需要将NaN转为None ,前端js可以识别null

        df = df.replace({np.nan: None})
        # logger.info('final df', final_df)

        # 6. 一键转为 Python 列表字典结构 (对应 JSON 中的 [{...}, {...}])
        # orient='records' 是关键，它会自动处理 Pandas 中的 NaN 值为 Python 的 None (即 JSON 的 null)
        json_structure = df.to_dict(orient='records')
        # logger.info('json_structure',json_structure)
        # logger.info('df.head: ',df.head())
        return json_structure
    except Exception as e:
        logger.error(f"查询失败: {e}")
    finally:
        influx_client.close()

