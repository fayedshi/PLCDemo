from enum import Enum


# 1. 定义一个作业状态的枚举
class JobStatus(Enum):
    PENDING = 1     # 等待中
    RUNNING = 2     # 运行中
    PAUSED = 3      # 已暂停
    SUCCESS = 4     # 成功结束
    FAILED = 5      # 失败结束

# 2. 如何使用它？
current_status = JobStatus.RUNNING
print(type(current_status))

# 3. 访问名字（Name）和具体值（Value）
print(current_status.name)   # 输出: "RUNNING" (字符串)
print(current_status.value)  # 输出: 2 (对应的值)

# 4. 类型安全检查
if current_status == JobStatus.RUNNING:
    print("🚨 作业正在安全运行中，请勿重复触发！")
