import asyncio
import json
from pyhfs import FusionSolarClient

async def main():
    # 1. 替换为你自己的华为北向接口服务器域名、API账号和密码
    # 注意：这里的密码对应系统里创建北向账号时设置的密码（systemCode）
    # https://uni01cn.fusionsolar.huawei.com/
    HOST = "cn.fusionsolar.huawei.com"
    USERNAME = "north_api_user"
    PASSWORD = "north@123"

    # 2. 初始化客户端
    # pyhfs 底层基于 asyncio（异步），所以需要配合 async/await 使用
    async with FusionSolarClient(host=HOST, username=USERNAME, password=PASSWORD) as client:
        try:
            print("正在连接华为智能光伏北向系统并登录...")
            
            # 3. 调用 get_station_list 获取电站列表
            # pyhfs 已经把 /thirdData/getStationList 封装为了符合 Python 命名的 get_station_list 方法
            stations = await client.get_station_list()
            
            # 4. 打印返回的电站数据
            print(f"成功获取到 {len(stations)} 个已授权的电站：\n")
            print(json.dumps(stations, indent=4, ensure_ascii=False))
            
            # 5. 提取核心字段示例：遍历并打印电站名称和电站编码(stationCode)
            for station in stations:
                name = station.get("stationName")
                code = station.get("stationCode")
                status = station.get("stationStatus")
                print(f"电站名称: {name} | 编码: {code} | 状态: {status}")

        except Exception as e:
            print(f"调用失败，错误信息: {e}")

# 运行异步主函数
if __name__ == "__main__":
    asyncio.run(main())
