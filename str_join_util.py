# print('test')
import time
import asyncio
async def build_influx_line_protocol(measurement, tags, fields, timestamp_ns=None):
    """
    动态将字典转换为 InfluxDB 3 标准行协议格式
    :param measurement: 表名 (str)
    :param tags: 标签字典 (dict)
    :param fields: 400个字段数据的字典 (dict)
    :param timestamp_ns: 纳秒时间戳，如果不传则使用当前时间
    """

    try:
        # print('within build_influx_line_protocol')
        # 1. 动态拼接 Tags (例如: device_id=plc_01,area=workshop_A)
        tag_str = ",".join([f"{k}={v}" for k, v in tags.items()])
        measurement_and_tags = f"{measurement},{tag_str}" if tag_str else measurement
        
        # 2. 动态拼接 400 个 Fields (例如: temp1=23.5,press2=101.3...)
        field_list = []
        for k, v in fields.items():
            if(v>50000):# innormal figure to skip
                print(f"****************************Invalid value found: {v}")
                print('PLC内部异常，等待2分钟...')
                await asyncio.sleep(120)
                raise Exception('【错误：】PLC读到异常数据')
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

        # timestamp_ns=1787304318447622000
        # 4. 组合成行协议：西门子数据_表名,标签 字段1=值1,字段2=值2 时间戳
        line = f"{measurement_and_tags} {field_str} {timestamp_ns}"
        # print(line)
        return line
    except Exception as e:
        raise Exception(f'build_influx_line_protocol 发生异常, {e}')