
from typing import Dict, Optional
import time

import httpx


# ==================== 🔑 华为北向连接单例管理器 ====================
USERNAME = "north_api_user"
PASSWORD = "north@123"
# BASE_URL = "https://cn.fusionsolar.huawei.com/thirdData"

class HuaweiSolarSingleAccountAPI:
    def __init__(self, domain: str = "://huawei.com"):
        self.client = httpx.AsyncClient(timeout=15.0)
        self.base_url = "https://cn.fusionsolar.huawei.com/thirdData"
        
        # 内部缓存唯一的 Token 状态
        self.xsrf_token: Optional[str] = None
        # self.cookie_str: Optional[str] = None
        self.last_login_time: float = 0
        self.token_expiry: float = 1800  # 假设华为 Token 20分钟过期

    async def _ensure_logged_in(self):
        """内部方法：确保当前有可用的 Token，如果失效了才去重新登录（保活机制）"""
        now = time.time()
        # 如果已经有 token 且没过期，直接复用，不需要重复登录
        if self.xsrf_token  and (now - self.last_login_time < self.token_expiry):
            print(f'复用已存在token: {self.xsrf_token}')
            return

        print("Token 不存在或已过期，正在向华为服务器发起登录...")
        url = f"{self.base_url}/login"
        payload = {"userName": USERNAME, "systemCode": PASSWORD}
        
        # 清空旧请求头，防止干扰登录
        self.client.headers.clear()
        
        response = await self.client.post(url, json=payload)
        res_json = response.json()
        
        if res_json.get("failCode") == 0 or res_json.get("success", True):
            self.xsrf_token = response.headers.get("xsrf-token")
            # self.cookie_str = response.headers.get("Set-Cookie")
            self.last_login_time = now
            print(f'获得token f{self.xsrf_token}')
            # 把共享的 Token 写入全局 Client
            self.client.headers.update({
                "XSRF-TOKEN": self.xsrf_token,
                # "Cookie": self.cookie_str,
                "Content-Type": "application/json"
            })
            print("全局唯一 Token 刷新/获取成功！")
        else:
            raise Exception(f"华为账号登录失败: {res_json}")

    async def get_station_list(self, page_no: int = 1) -> Dict:
        """
        所有本地用户最终都调用这个方法。
        无论谁调用，内部都会自动复用或刷新那唯一的一个 Token。
        """
        # 1. 确保全局 Token 有效
        await self._ensure_logged_in()
        
        # 2. 直接发起请求（Headers 已经在 _ensure_logged_in 中配置好了）
        url = f"{self.base_url}/stations"
        payload = {"pageNo": page_no}
        
        response = await self.client.post(url, json=payload)
        print(f' get_station_list response: {response.json()}')
        # 305表示过期token 过期，需要重新登录
        if response.json()['failCode'] == 305:
            print(f'305 需要重新登录')
            self.xsrf_token = None # 置空xsrf token
            # await self._ensure_logged_in()
        return response.json()

    async def get_power_by_dimension(self, plant_codes, dimension, collect_time) -> Dict:
            """
            所有本地用户最终都调用这个方法。
            无论谁调用，内部都会自动复用或刷新那唯一的一个 Token。
            """
            # 1. 确保全局 Token 有效
            await self._ensure_logged_in()
            
            # 2. 直接发起请求（Headers 已经在 _ensure_logged_in 中配置好了）
            url = f"{self.base_url}/getKpiStation{dimension}"
            print(f'url {url}')

            payload = {
                        "stationCodes": plant_codes,
                        "collectTime": collect_time
                    }
            response = await self.client.post(url, json=payload)
            print(f' getKpiStation response: {response.json()}')
            if response.json()['failCode'] == 305:
                self.xsrf_token = None
                # await self._ensure_logged_in()
            return response.json()
# 销毁时机：会伴随整个 Python 进程（Web 服务）直到程序彻底退出时才会被销毁。
solar_api_instance = HuaweiSolarSingleAccountAPI()