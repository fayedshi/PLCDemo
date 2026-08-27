####################
# upsert语法python
####################

from influxdb_client_3 import InfluxDBClient3, Point

# 1. 初始化 3.x 客户端
client = InfluxDBClient3(
    host="http://localhost:8181", 
    token="YOUR_TOKEN", 
    database="factory_db"
)

# 2. 模拟要修正的那条数据的绝对精确时间戳
#（必须精确到您存进去时的那一个微秒或纳秒，通常来自您的传感器时间记录）
target_time = 1767225600000000000  

# 3. 构造一模一样 Tag 信息的 Point，直接调用 write 写入
# 只要 measurement、tag、time 三者对齐，就是完美的 Upsert 语句
fix_point = (
    Point("plc_temp_data")
    .tag("plc_type": "s7-smart200"),
    .tag("station_id", "line_01"),       # 👈 必须与原数据相同
    .field("temperature", 25.4)   # 👈 写入最新的正确值（更新）
    .field("status", 1),
    .time(target_time)            # 👈 必须与原数据相同
)

client.write(record=fix_point)
print("【Upsert 成功】数据已在底层自动完成覆盖更新")
