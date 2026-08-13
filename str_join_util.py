# print('test')
import time
def build_influx_line_protocol(measurement, tags, fields, timestamp_ns=None):
    """
    动态将字典转换为 InfluxDB 3 标准行协议格式
    :param measurement: 表名 (str)
    :param tags: 标签字典 (dict)
    :param fields: 400个字段数据的字典 (dict)
    :param timestamp_ns: 纳秒时间戳，如果不传则使用当前时间
    """

    # print('within build_influx_line_protocol')
    # 1. 动态拼接 Tags (例如: device_id=plc_01,area=workshop_A)
    tag_str = ",".join([f"{k}={v}" for k, v in tags.items()])
    measurement_and_tags = f"{measurement},{tag_str}" if tag_str else measurement
    
    # 2. 动态拼接 400 个 Fields (例如: temp1=23.5,press2=101.3...)
    field_list = []
    for k, v in fields.items():
        if(v>50000):# innormal figure to skip
            print(f"****************************unnormal value occured: {v}")
            return ''
        if isinstance(v, float):
            field_list.append(f"{k}={v}")  # 浮点数直接拼接
        elif isinstance(v, int):
            field_list.append(f"{k}={v}i") # 整数需要加 i 后缀
        elif isinstance(v, str):
            field_list.append(f'{k}="{v}"') # 字符串需要加双引号
            
    field_str = ",".join(field_list)
    
    # 3. 处理时间戳 (默认为当前纳秒时间戳)
    if timestamp_ns is None:
        timestamp_ns = time.time_ns()
        
    # 4. 组合成行协议：西门子数据_表名,标签 字段1=值1,字段2=值2 时间戳
    line = f"{measurement_and_tags} {field_str} {timestamp_ns}"
    # print(line)
    return line

# === 模拟从西门子 PLC 采集到 400 个浮点数寄存器 ===
# 假设我们通过之前的方法，解出了 400 个传感器的实时浮点数值
# plc_channels = {}
# for i in range(1, 401):
#     plc_channels[f"sensor_ch{i}"] = 23.45 + (i * 0.1)  # 模拟数据如: 23.55, 23.65...

# # 元数据标签
# device_tags = {
#     "plc_type": "s7-1200",
#     "station_id": "line_01"
# }

# # 动态生成 400 个字段的行协议数据
# influx_data_line = build_influx_line_protocol(
#     measurement="plc_raw_data", 
#     tags=device_tags, 
#     fields=plc_channels
# )

# # 打印前 200 个字符看看结构
# print("生成的动态行协议数据样例：")
# print(influx_data_line[:200] + " ... [后面还有几百个字段] ... " + influx_data_line[-30:])
