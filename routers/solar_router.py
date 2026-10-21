from fastapi import APIRouter, HTTPException, Depends, Query
import httpx
# import pyhfs
from typing import Dict, Any
import httpx
import time
from typing import Dict, Optional
from date_util import datetime_to_ms, ms_to_datetime
from huawei_solar_api import solar_api_instance

import requests
from logger.demo_logger import logger


# router = APIRouter(prefix="/api/v1/solar", tags=["华为光伏数据"])
router = APIRouter(tags=["华为光伏数据"])

BASE_URL = "https://cn.fusionsolar.huawei.com/thirdData"

async def get_async_client():
    async with httpx.AsyncClient() as client:
        yield client

async def fetch_xsrftoken(client: httpx.AsyncClient):
    try:
        # session = requests.Session()
        headers = {
            # "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json"
        }
        # 2. 登录获取 Token
        # ⚠️ 华为限制：10分钟内最多登录5次，切勿在循环或高频请求中重复执行此登录步骤
        response = await client.post(
            f"{BASE_URL}/login", 
            json={"userName": USERNAME, "systemCode": PASSWORD},
            headers = headers
        )

        # 打印 HTTP 状态码（应该为 200）
        print(f"HTTP状态码: {response.status_code}")
    
        # print(f"reponse: {response.text[:500]}")
        res_json = response.json()
        print(f"服务器返回内容: {res_json}, fail code{res_json['failCode']}")

        if res_json.get("success") is True:
            xsrf_token = response.headers.get("xsrf-token")
            print(f"🎉 登录成功！获取到的 Token 为: {xsrf_token}")
            return xsrf_token
        else:
            fail_code = res_json.get("failCode")
            message = res_json.get("message")
            print(f"❌ 登录失败！华为返回的错误码(failCode): {fail_code}，提示信息: {message}")
    except Exception as e: 
        logger.error(f'获取xsrf token请求异常 {e}')
        return None
    

@router.get("/api/stations")
async def get_stations():
    
    try:
    #     xsrf_token = await fetch_xsrftoken(client)
    #     if not xsrf_token:
    #         raise Exception('未获取token')
    #     # todo: more than 1 page
    #     stations_resp = await client.post(f"{BASE_URL}/stations",
    #             headers={"XSRF-TOKEN": xsrf_token, "Content-Type": "application/json"},
    #             json={"pageNo": 1} # 最小请求体，查询第1页数据 不传 并网开始时间，则返回分页数据"gridConnectedStartTime":1701561600000
    #         )
    #     station_json= stations_resp.json()
    #     stations=[]
    #     for station in station_json.get("data").get("list", []):
    #         plant={}
    #         plant['code']=station['plantCode']
    #         plant['name']=station['plantName']
    #         stations.append(plant)
    #     logger.info(f'station list: {stations}')
    #     return stations 
   
        station_json = await solar_api_instance.get_station_list(1)
        stations=[]
        for station in station_json.get("data").get("list", []):
            plant={}
            plant['code']=station['plantCode']
            plant['name']=station['plantName']
            stations.append(plant)
        logger.info(f'station list: {stations}')
        return stations 
    except Exception as e: 
        logger.error(f'get_stations异常 {e}')
        return None
    
# 按小时，日、天，月
@router.get("/api/solar")
async def get_power_supply_data(plant_code, dimension, input_time):
    
    try:
        millisecs= datetime_to_ms(input_time, fmt="%Y-%m-%dT%H:%M:%S.%fZ")
        logger.info(f'millisc {millisecs}')
        power_json = await solar_api_instance.get_power_by_dimension(plant_code,dimension, millisecs)
        # stations=[]
        data_items=list(power_json.get("data"))
        dim_fmt_map={'Day':'%Y-%m-%d',"Hour": '%Y-%m-%d %H', 'Month': '%Y-%m', 'Year':'%Y'}
        # logger.info(f"collecttime:{item['dataItemMap'].get('collectTime')}")
        power_list= [{'time': ms_to_datetime(item['collectTime'],dim_fmt_map[dimension]), 'power': item["dataItemMap"].get('PVYield',0)}  for item in data_items]
            # plant={}
            # plant['code']=
            # plant['name']=item['plantName']
            # stations.append(plant)
        logger.info(f'powerlist: {power_list}')
        return power_list 
    except Exception as e: 
        logger.error(f'get_power_supply_data异常 {e}')
        return []
    

@router.get("/realtime-kpi")
async def get_solar_realtime_data():
    """
    前端 Vue3 看板专用的电站实时数据抓取接口
    """
    client = solar_manager.get_client()
    
    try:
        # 1. 拿到账号关联的所有电站
        plants_data = client.get_plant_list()
        
        # 2. 提取第一个电站的编号（根据你的实际业务调整）
        if not plants_data or 'data' not in plants_data or len(plants_data['data']) == 0:
            return {"status": "SUCCESS", "message": "该账号下未关联任何光伏电站", "data": {}}
            
        station_code = plants_data['data'][0]['stationCode']
        
        # 3. 抓取该电站实时关键指标
        kpi_data = client.get_plant_kpi_realtime(station_code)
        
        # 4. 数据清洗：组装成前端好读的精简 JSON
        # 注意：pyhfs 返回的原始格式与华为官方 Reference V6 文档完全一致
        raw_metrics = kpi_data.get('data', {})
        
        return {
            "status": "SUCCESS",
            "station_name": plants_data['data'][0].get('stationName'),
            "metrics": {
                "active_power": raw_metrics.get("active_power", 0),       # 当前实时功率 (kW)
                "day_cap": raw_metrics.get("day_cap", 0),                 # 今日发电量 (kWh)
                "total_cap": raw_metrics.get("total_cap", 0),             # 历史总发电量 (kWh)
                "co2_reduction": raw_metrics.get("co2_reduction", 0)       # 二氧化碳减排量 (吨)
            }
        }
        
    except Exception as e:
        # 💥 善后机制：如果遇到类似于 Token 过期导致的报错，直接将连接清空，下次请求会自动重新走握手流程
        print(f"华为接口调用抽风: {e}")
        solar_manager.reset_connection()
        raise HTTPException(status_code=500, detail="调取光伏电站实时指标失败，正在尝试重连重试")


# @router.get("/history")
# async def get_solar_history(
#     time_type: str = Query(..., description="查询类型: hour, day, month"),
#     station_code: str = "NE=12345678"  # 你的华为电站编号
# ):
#     """
#     【图表专用接口】根据小时、天、月，清洗华为光伏数据，统一输出给前端 ECharts
#     """
#     # 💡 真实业务中：这里需要调 client.get_history_kpi(...) 
#     # 华为接口需要传入开始/结束时间戳（毫秒），并且 hour, day, month 的指标 ID 略有不同（如 product_power, day_cap）
    
#     x_axis = []
#     y_axis = []
    
#     now = datetime.now()
    
#     try:
#         if time_type == "hour":
#             # 🕒 按小时：展示今天 0点 到 当前小时 的发电功率趋势 (kW)
#             current_hour = now.hour
#             for h in range(0, current_hour + 1):
#                 x_axis.append(f"{h}:00")
#                 # 模拟光伏曲线：中午功率最高，早晚为 0
#                 if 6 <= h <= 18:
#                     power = round(random.uniform(50.0, 150.0) * (1 - abs(12-h)/7), 2)
#                     y_axis.append(max(0.0, power))
#                 else:
#                     y_axis.append(0.0)
#             chart_title = "当日实时发电功率 (kW)"
#             series_name = "实时功率"

#         elif time_type == "day":
#             # 📅 按日：展示最近 15 天每天的发电量 (kWh)
#             for i in range(14, -1, -1):
#                 date_str = (now - timedelta(days=i)).strftime("%m-%d")
#                 x_axis.append(date_str)
#                 y_axis.append(round(random.uniform(300.0, 600.0), 1))
#             chart_title = "近15日发电量趋势 (kWh)"
#             series_name = "日发电量"

#         elif time_type == "month":
#             # 🗓️ 按月：展示今年 1月 到当前月份的发电量 (kWh)
#             current_month = now.month
#             for m in range(1, current_month + 1):
#                 x_axis.append(f"{m}月")
#                 y_axis.append(round(random.uniform(8000.0, 15000.0), 1))
#             chart_title = "今年各月发电量统计 (kWh)"
#             series_name = "月发电量"
#         else:
#             raise HTTPException(status_code=400, detail="不支持的查询类型")

#         # 统一输出极其干净的数据结构，前端直接闭眼渲染
#         return {
#             "status": "SUCCESS",
#             "title": chart_title,
#             "series_name": series_name,
#             "xAxis": x_axis,
#             "yAxis": y_axis
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"调取华为历史指标失败: {e}")