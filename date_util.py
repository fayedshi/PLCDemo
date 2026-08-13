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
