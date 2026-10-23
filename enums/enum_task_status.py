from enum import IntEnum

class TaskStatus(IntEnum):
    # 格式：常量名 = (整数值, "中文描述")
    WAITING_TO_TRIGGER = (-1, "等待触发")
    RUNNING = (0, "运行中")
    SUCCESS = (1, "正常结束")
    TRIGGER_TIMEOUT = (2, "等待触发超时")
    END_TIMEOUT = (3, "等待结束超时")
    CANCELLED = (4, "被取消")
    ABORTED = (5, "异常中止")

    def __new__(cls, value, description):
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.description = description  # 绑定中文描述
        return obj

    @property
    def is_finished(self) -> bool:
        """判断任务是否已结束"""
        return self._value_ >= 1


print(TaskStatus.END_TIMEOUT.name)