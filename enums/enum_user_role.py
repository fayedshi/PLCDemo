from enum import Enum


# 1. 定义一个作业状态的枚举
# control','windows', 'dampers', 'blowers','exhaustFans','airConditioners'
class UserRole(Enum):
    ADMIN=(1,'系统管理员')     
    PLAIN_USER=(2,'一般用户') 