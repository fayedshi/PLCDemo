from datetime import datetime, timezone,timedelta

def to_utctime(time_str:str):

    # 替换 Z 为 +00:00 后解析（兼容 Python 3.10 以下）
    dt = datetime.fromisoformat(time_str)

    # end_time = dt + timedelta(minutes=20)

    # print('dt ',dt)
    # 确保是 UTC 时区
    dt_utc = dt.astimezone(timezone.utc).isoformat().replace('+00:00','Z')

    # dt_utc = dt.astimezone(timezone.utc).isoformat()
    return dt_utc


def to_localtime(utc_time:str, fmt: str):
    print('in function',utc_time)
    dt = datetime.strptime(utc_time, fmt)
    return dt+timedelta(hours=8)

# def timeAdd(unit:int, amount:int):
#     dt + timedelta(minutes=20)

if __name__ == "__main__":
    time_str = "2023-10-01T15:08"
    dt_utc = to_utctime(time_str)
    print(dt_utc)  # 2023-10-01 15:08:00+00:00
    print(to_localtime('26-08-13 02:00','%y-%m-%d %H:%M'))
    # print('end_time',end_time)

from datetime import datetime, timezone, timedelta

# 定义标准的北京时区 (东八区)
SHA_TZ = timezone(timedelta(hours=8))

def datetime_to_ms(date_str: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> int:
    """
    将指定格式的日期字符串转换为北京时间的13位毫秒时间戳
    :param date_str: 日期字符串，例如 "2026-10-10 00:00:00"
    :param fmt: 字符串的格式，默认为 "年-月-日 时:分:秒"
    :return: 13位整数毫秒时间戳
    """
    # 1. 将字符串解析为 datetime 对象
    dt = datetime.strptime(date_str, fmt)
    # 2. 强制指定为北京时区，防止服务器时区干扰
    dt = dt.replace(tzinfo=SHA_TZ)
    # 3. dt.timestamp() 获取的是秒级浮点数，乘以 1000 并转为 int 得到毫秒
    return int(dt.timestamp() * 1000)


def get_current_ms() -> int:
    """
    直接获取当前时间的13位毫秒时间戳（常用于华为历史数据查询的 endTime）
    """
    return int(datetime.now(SHA_TZ).timestamp() * 1000)

def ms_to_datetime(ms_timestamp: int, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    将13位毫秒级时间戳转换为指定格式的北京时间字符串
    :param ms_timestamp: 13位整数时间戳，如 1791561600000
    :param fmt: 输出的日期格式，默认为 "年-月-日 时:分:秒"
    :return: 格式化后的时间字符串
    """
    # 1. 将13位毫秒转为秒级浮点数
    seconds = ms_timestamp / 1000.0
    
    # 2. 将秒级时间戳转换为带北京时区的 datetime 对象
    dt = datetime.fromtimestamp(seconds, tz=SHA_TZ)
    
    # 3. 格式化为字符串输出
    return dt.strftime(fmt)


# ================= 演示调用 =================
if __name__ == "__main__":
    # 测试你刚才要的 2026-10-10
    t1 = datetime_to_ms("2025-10-10 00:00:00")
    print(f"2025-10-10 00:00:00 转换结果: {t1}")  # 输出: 1791561600000
    
    t2 = datetime_to_ms("2026-10-10 23:59:59")
    print(f"2026-10-10 23:59:59 转换结果: {t2}")  # 输出: 1791647999000

    # 快捷支持其他格式
    t3 = datetime_to_ms("20261010", fmt="%Y%m%d")
    print(f"纯数字日期 20261010 转换结果: {t3}")    # 输出: 1791561600000
    
    print(f"当前时间毫秒戳: {get_current_ms()}")

    print(f'1501862400000 to  time: {ms_to_datetime(1501862400000)}')
    print(f'1503046597854 to  time: {ms_to_datetime(1501884000000)}')
