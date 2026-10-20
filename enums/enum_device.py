from enum import Enum


# 1. 定义一个作业状态的枚举
# control','windows', 'dampers', 'blowers','exhaustFans','airConditioners'
class Device(Enum):
    # control = 1     
    windows = 1     
    dampers = 2     
    blowers = 3     
    exhaustFans = 4   
    airConditioners =5
# 2. 如何使用它？
current_device = Device.blowers
print(type(current_device))

# 3. 访问名字（Name）和具体值（Value）
print(f'name: {current_device.name}')   # 输出: "RUNNING" (字符串)
print('value',Device.windows.value)  # 输出: 2 (对应的值)
cates=  [dev for dev in  Device.__members__]
print(cates)
for mem in Device.__members__:
    print(f'mem: {mem}')

for dev in Device:
    print(f'dev full: {dev}')
# 4. 类型安全检查
if current_device == Device.airConditioners:
    print("🚨 作业正在安全运行中，请勿重复触发！")

