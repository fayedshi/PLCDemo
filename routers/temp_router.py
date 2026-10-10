from fastapi import APIRouter, Request, Query

from datetime import timedelta

from fastapi import APIRouter, Query, Request

from influxdb_client_3 import InfluxDBClient3
import numpy as np
import pandas as pd

from date_util import to_utctime

from fastapi import APIRouter, Query
from logger.demo_logger import logger

# 创建数据库表

# Base.metadata.create_all(bind=engine)

# app = FastAPI(title="Python CRUD System", description="基于FastAPI和SQLAlchemy的增删改查示例")

# router = APIRouter(prefix="/gran", tags=["仓房管理模块"])
router = APIRouter()


@router.get("/api/tempreport")
def show_cords_temp(request: Request, input_time: str, house_code: str):
    logger.info(f'input_time: {input_time}')
    influx_client=InfluxDBClient3(host=request.app.state.influx_db_url, token=request.app.state.influx_token, database="my_db")
    
    # input_time = obj.get('input_time')
    # start_time = f"{input_time}:00Z"
    # dt_obj = datetime.fromisoformat(input_time)
    # new_dt_obj = dt_obj + timedelta(minutes=1)
    # end_time = new_dt_obj.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    temp_cols = [f"temp{i}" for i in range(140)]
    temp_all_cols = ", ".join(temp_cols)

    if not input_time:
        query = f"""
            SELECT {temp_all_cols},time FROM plc_temp_data 
            WHERE station_id= '{house_code}' and time >= NOW() - INTERVAL '1 day'
            order by time desc limit 1
            """
    else:
        start_time=to_utctime(input_time)
        query = f"""
            SELECT {temp_all_cols}, time 
            FROM plc_temp_data 
            WHERE station_id= '{house_code}' and time >= '{start_time}' 
            order by time asc
            limit 1
            """

    # 3. 执行查询并转换数据
    try:
        # language="sql" 显式指定使用 SQL引擎
        logger.info('to exectue',query)
        table = influx_client.query(query=query, language="sql")

        # 4. 将 PyArrow Table 转换为 Pandas DataFrame
        if table.num_rows == 0:
            return pd.DataFrame()
        # 将 PyArrow Table 转换为 Pandas DataFrame 以便后续分析
        df = table.to_pandas()
        logger.info(f'found data, {df}')
        logger.info(f"查询到 {len(df)} 条数据")
        # logger.info('df.head: ',df.head())
        return df.to_dict(orient="records")[0]
    except Exception as e:
        logger.error(f"查询失败: {e}")
    finally:
        influx_client.close()


@router.get("/api/temp-trend")
def get_history_data(request: Request,start_time: str,end_time: str, layer: int, options: list[str] = Query([])):
    influx_client=InfluxDBClient3(host=request.app.state.influx_db_url, token=request.app.state.influx_token, database="my_db")
    logger.info(f'start_time: {start_time},options: {options}')
    # 1. 动态生成 140 个列名的列表：['temp0', 'temp1', ..., 'temp139']
    
    step = 1 if layer == -1 else 4
    start_index = 0 if layer == -1 else layer
    
    full_len= 140
    partial_len= int(140/step)
    temps_arr = [f"temp{i}" for i in range(start_index, full_len, step)]
    
    str_temp_sum = " + ".join(temps_arr)
    str_temps_arr=",".join(temps_arr)

    min_temp_clause= f"ROUND(MIN(LEAST({str_temps_arr}))/10.0,1) AS min_temp"
    max_temp_clause =f"ROUND(MAX(GREATEST({str_temps_arr}))/10.0,1) AS max_temp"
    avg_temp_clause= f"ROUND(AVG(({str_temp_sum}) / {partial_len})/10.0, 1) AS avg_temp"
            
    clauses=[]
    temp_clauses=[]
    humid_clauses=[]
    
    humid_cols = [f"humid{i}" for i in range(start_index, full_len, step)]
    str_humid_sum = " + ".join(humid_cols)
    str_humid_cols=",".join(humid_cols)
    min_humid_clause= f"ROUND(MIN(LEAST({str_humid_cols}))/10.0,1) AS min_humid"
    max_humid_clause =f"ROUND(MAX(GREATEST({str_humid_cols}))/10.0,1) AS max_humid"
    avg_humid_clause= f"ROUND(AVG(({str_humid_sum}) / {partial_len})/10.0, 1) AS avg_humid"

    if 'min' in options:
        # clauses.append(min_temp_clause)
        # clauses.append(min_humid_clause)
        temp_clauses.append(min_temp_clause)
        humid_clauses.append(min_humid_clause)

    if 'avg' in options:
        # clauses.append(avg_temp_clause)
        # clauses.append(avg_humid_clause)
        temp_clauses.append(avg_temp_clause)
        humid_clauses.append(avg_humid_clause)

    if 'max' in options:
        # clauses.append(max_temp_clause)
        # clauses.append(max_humid_clause)
        temp_clauses.append(max_temp_clause)
        humid_clauses.append(max_humid_clause)

    clauses_str= ", ".join(clauses)
    temp_clause_str= ", ".join(temp_clauses)
    humid_clause_str= ", ".join(humid_clauses)
    start = to_utctime(start_time)
    end = to_utctime(end_time)

    # query = f"""
    #     SELECT 
    #         {clauses_str},
    #         DATE_BIN(INTERVAL '10 minutes', a.time, TIMESTAMP '1970-01-01 00:00:00') chart_time 
    #     FROM plc_temp_data a left join plc_humid_data b 
    #         on DATE_BIN(INTERVAL '10 minutes', a.time, TIMESTAMP '1970-01-01 00:00:00')=DATE_BIN(INTERVAL '10 minutes', b.time, TIMESTAMP '1970-01-01 00:00:00') 
    #     where 
    #         a.time between '{start}' AND '{end}' 
    #         AND b.time BETWEEN '{start}' AND '{end}' 
    #         and a.temp0 is not null
    #     group by chart_time 
    #     order by chart_time ASC
    #     """
    query = f"""
        WITH temp_aligned AS (
            SELECT 
                {temp_clause_str},
                DATE_BIN(INTERVAL '10 minutes', time, TIMESTAMP '1970-01-01 00:00:00') AS chart_time
            FROM plc_temp_data
            WHERE time BETWEEN '{start}' AND '{end}' AND temp0 IS NOT NULL
            GROUP BY chart_time
        ),
        humid_aligned AS (
            SELECT 
                {humid_clause_str},
                DATE_BIN(INTERVAL '10 minutes', time, TIMESTAMP '1970-01-01 00:00:00') AS chart_time
            FROM plc_humid_data
            WHERE time BETWEEN '{start}' AND '{end}' 
            GROUP BY chart_time
        )
        
        SELECT 
            
            a.avg_temp, b.avg_humid,
            
            a.chart_time
        FROM temp_aligned a
        LEFT JOIN humid_aligned b ON a.chart_time = b.chart_time 
        
        ORDER BY a.chart_time ASC
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
        logger.info(f'found data, {df}')
        # logger.info(f"查询到 {len(df)} 条数据")
        df['time'] = pd.to_datetime(df['chart_time']) + timedelta(hours=8)
        df['time'] = df['time'].dt.strftime('%y-%m-%d %H:%M')
     
        
        # 5. 核心：只筛选前端需要的 4 列
        # final_df = df[['time', 'avg', 'min', 'max']]
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

