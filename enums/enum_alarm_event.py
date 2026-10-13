from enum import Enum


# 1. 定义一个作业状态的枚举
# control','windows', 'dampers', 'blowers','exhaustFans','airConditioners'
class AlarmType(Enum):
    TEMP_HIGH = 1
    PLC_DISCONNECT = 2     
    DEVICE_MALFUNCTION = 3 


