import pyhfs

# 🔑 你的华为北向专门账号与密码（参见上一步在“北向管理”中创建的凭证）
USER = "north_api_user"
PASSWORD = "north@123"

try:
    # 🎯 使用上下文管理器建立连接会话
    with pyhfs.ClientSession(user=USER, password=PASSWORD) as client:
        
        # 1. 抓取该账号管辖的所有光伏电站列表
        plants = client.get_plant_list()
        print("--- 电站列表数据 ---")
        print(plants)
        
        # 2. 如果你想获取特定电站的实时运行指标（KPI）
        # 实际开发中，需要从 plants 列表中提取真实存在的 stationCode
        if plants and 'data' in plants:
            station_code = plants['data'][0].get('stationCode')
            
            # 抓取电站级当日发电量、当前功率等数据
            plant_kpi = client.get_plant_kpi_realtime(station_code)
            print(f"--- 电站 {station_code} 实时数据 ---")
            print(plant_kpi)

except pyhfs.LoginFailed:
    # 💥 华为接口账号密码错误时会抛出这个专用异常
    print("❌ 登录失败！请检查华为智能光伏北向账号与密码。")
except Exception as e:
    print(f"❌ 通信或系统发生异常: {e}")
