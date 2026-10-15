from datetime import timedelta

from influxdb_client_3 import InfluxDBClient3
import numpy as np
import pandas as pd

from date_util import to_utctime

from logger.demo_logger import logger

from fastapi import APIRouter, HTTPException, status
import httpx  # 🔑 引入专门用来在后端发请求的库
from pydantic import BaseModel
from typing import List


router = APIRouter(tags=["粮仓门禁代理"])
batch_dev_address={'window':31,'door':32}


# 后端自己内部掌握的第三方凭证（绝对不暴露给前端）
THIRD_PARTY_AUTH = {
    "username": "admin",
    "password": "admin123",
    "base_url": "http://192.168.0.100" 
}

# class OpeningLogOut(BaseModel):
#     id: int
#     granary_id: str
#     operator: str
#     open_time: str
#     status: str

# class LogsResponse(BaseModel):
#     items: List[OpeningLogOut]
#     total: int

@router.get("/api/granary-entry-logs")
async def get_granary_logs_proxy(page: int, page_size:int):
    """
    【正规写法】前端唯一的获取数据接口。
    登录第三方、抓取数据、清洗格式全部由后端一条龙完成！
    """
    # 异步网络客户端，用来调第三方
    async with httpx.AsyncClient() as client:
        try:
            # 步骤 1: 后端自己在后台登录第三方系统
            login_res = await client.post(
                f"{THIRD_PARTY_AUTH['base_url']}/api/v1/auth/login", 
                json={"username": THIRD_PARTY_AUTH["username"], "password": THIRD_PARTY_AUTH["password"]}
            )
            if login_res.status_code != 200:
                raise HTTPException(status_code=502, detail="第三方平台认证失败")
                
            token = login_res.json().get('data').get("token")

            # 步骤 2: 后端携带拿到的 Token，去请求第三方的真实开仓记录
            logs_res = await client.get(
                f"{THIRD_PARTY_AUTH['base_url']}/api/v1/door-record?page={page}&pageSize={page_size}",
                headers={"Authorization": f"Bearer {token}"}
            )
            if logs_res.status_code != 200:
                raise HTTPException(status_code=502, detail="无法从查粮门禁系统获取记录")

            # 步骤 3: 拿到原始数据后，进行数据清洗与提取
            remote_data = logs_res.json() # 假设结构为 {"data": [...], "count": 10}
            logger.info(f'remote_data: {remote_data}')
            cleaned_items = []
            usernames=[]
            for item in remote_data.get("data").get("list", []):
                # 转化、提取为前端 Element Table 刚好需要的精简字段
                for i in range(1,4):
                    if item.get(f"username{i}") !='null':
                        usernames.append(item.get(f"username{i}"))
                usernames_str = ", ".join(usernames)  
                logger.info(f'usernamestr: {usernames_str}')
                cleaned_items.append({
                    "id": item.get("id"),
                    "granary_id": item.get("granaryId"),
                    "dev_serial": item["device"]['deviceId'],
                    "silo_name": f"{item['granary']['houseName']}({item['granary']['depotName']})",
                    "open_type": item.get("openType"),
                    # 设备端id
                    "dev_id": item.get("devId"),
                    "operators": usernames_str,
                    "open_time": item.get("recordTime"),
                    "status": "SUCCESS" if item.get("openState")== 0 else "FAILED"
                })
                usernames=[]
            return {"items": cleaned_items, "pagination": remote_data["data"]["pagination"]}
            # return cleaned_items

        except httpx.RequestError as exc:
            # 💥 针对第三方服务宕机/网络断开的防呆异常捕获
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"⚠️ 🛠️ 无法连接至第三方粮仓系统: {exc}"
            )
