from enum import Enum


# 1. 定义一个作业状态的枚举
# control','windows', 'dampers', 'blowers','exhaustFans','airConditioners'
class UserRole(Enum):
    SUPER_ADMIN = (1, '超级管理员')  # 可选：如果后续需要最高权限
    ADMIN = (2, '系统管理员')
    STAFF = (3, '标准用户')   # 一般员工
    # 是否要增加无需登录的访客

    def __init__(self, code, description):
        self.code = code                # 专属属性：角色代码
        self.description = description  # 专属属性：角色名称

print(UserRole.ADMIN.code)         # 输出: 2
print(UserRole.ADMIN.name)  # 输出: ADMIN
print(UserRole.ADMIN.description)  # 输出: 系统管理员
print(UserRole.ADMIN.value)        # 输出: (2, '系统管理员') 
print(UserRole.ADMIN)        # 输出       