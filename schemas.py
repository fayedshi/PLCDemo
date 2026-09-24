from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


# 🟢 基础模型（共用属性）
class GranaryBase(BaseModel):
    code: str = Field(..., example="AJ-001")
    name: str = Field(..., example="1号仓北廒间")
    capacity: int = Field(..., ge=1, example=3500)
    keeper: str = Field(..., example="张利国")
    grain_type: str = Field(..., example="小麦")
    max_temp: float = Field(..., example=22.0)
    plc_code: str = Field(..., example="001")
    

# ➕ 用于前端【创建】时传入的模型
class GranaryCreate(GranaryBase):
    pass

#  用于前端【修改】时传入的模型
class GranaryUpdate(GranaryBase):
    pass

# 用于给前端【返回】展示的模型（带有数据库自动生成的 ID）
class GranaryOut(GranaryBase):
    id: int

    class Config:
        from_attributes = True  # 允许兼容 SQLAlchemy 模型自动转换


class AlarmLogBase(BaseModel):
    # id: int = Field(..., description="", example="TEMP_HIGH")
    type: str = Field(..., description="报警类型", example="TEMP_HIGH")
    house_code: str = Field(..., description="粮仓代码", example="001")
    message: str = Field(..., description="报警消息文本")
    trigger_time: datetime = Field(default_factory=datetime.now)
    # 必填，默认未确认，未清除
    ack: bool = False
    cleared: bool = False
    # 可为空，默认为 None
    ack_time: Optional[datetime] = None
    clear_time: Optional[datetime] = None

    class Config:
    # 💡 必须开启：允许 Pydantic 自动解析 SQLAlchemy 的 ORM 对象
        from_attributes = True  # 在老版本 Pydantic 中是 orm_mode = True

class AlarmLogCreate(AlarmLogBase):
    
    """
    专用于插入/创建时的 Schema
    """
    # 💡 兼容处理：允许传入纯文本字符串时间（如 "2026-09-09 17:51:00"）或 datetime 对象
    # time: Optional[datetime] = Field(default_factory=datetime.now, description="报警时间")
    pass

class AlarmLogResponse(BaseModel):
    """
    专用于从数据库查询出来、返回给 Vue 前端时的 Schema
    """
    historyTotal: int      # 🎯 前端需要的总条数变量名
    items: List[AlarmLogBase] # 当前页的报警数组


# 1. 基础 Schema（定义公共字段和校验规则）
class VentilationModeBase(BaseModel):
    name: str = Field(..., max_length=50, description="模式名称")
    start_temp_diff: float = Field(..., description="起始温差")
    start_humidity_diff: float = Field(..., description="起始湿度差")
    end_temp_diff: float = Field(..., description="结束温差")
    end_humidity_diff: float = Field(..., description="结束湿度差")

# 2. 用于创建（POST 请求）的 Schema
class VentilationModeCreate(VentilationModeBase):
    pass  # 字段与 Base 一致

# 3. 用于部分更新（PATCH 请求）的 Schema（所有字段变为可选）
class VentilationModeUpdate(VentilationModeBase):
    # name: Optional[str] = Field(None, max_length=50, description="模式名称")
    # start_temp_diff: Optional[float] = Field(None, description="起始温差")
    # start_humidity_diff: Optional[float] = Field(None, description="起始湿度差")
    # end_temp_diff: Optional[float] = Field(None, description="结束温差")
    # end_humidity_diff: Optional[float] = Field(None, description="结束湿度差")
    pass

# 4. 用于返回数据（Response）的 Schema
class VentilationModeOut(VentilationModeBase):
    id: int = Field(..., description="自增主键 ID")

    class Config:
        # 允许直接从 SQLAlchemy 等 ORM 模型对象中读取数据转换
        from_attributes = True  # 注：如果使用 Pydantic v2，请改为 from_attributes = True

# 通用的分页结果包装 Schema
class VentilationModePageResult(BaseModel):
    total: int = 0  # 总数据量
    items: List[VentilationModeOut] = []  # 当前页的数据列表

    class Config:
        from_attributes = True  # Pydantic v1 写法（v2 请改为 from_attributes = True）


# 1. 基础模型（定义通用和核心的业务字段）
class VentiTaskBase(BaseModel):
    # max_length=50 严格对应 String(50) 的长度校验
    house_code: str= Field(..., max_length=10, description="仓房代码")
    mode_id: Optional[int] = Field(..., description="模式ID")
    mode_name: Optional[str] = Field(..., max_length=50, description="模式名称")
    status_code: int = Field(..., description="状态代码")
    status_text: str = Field(..., max_length=50, description="状态信息")

# 2. 创建模型（用于前端 POST 请求创建任务，通常由自增主键和时间，不需要前端传）
class VentiTaskCreate(VentiTaskBase):
    create_time: Optional[datetime] = Field(None, description="创建时间")
    

# 3. 更新模型（用于前端 PUT/PATCH 请求修改任务，所有字段变为可选）
class VentiTaskUpdate(BaseModel):
    mode_name: Optional[str] = Field(None, max_length=50, description="模式名称")
    status_code: Optional[int] = Field(None, description="状态代码")
    status_text: Optional[str] = Field(None, max_length=50, description="状态信息")
    update_time: Optional[datetime] = Field(None, description="更新时间")

# 4. 响应模型（用于后端返回给前端，包含数据库自动生成的 id、时间等完整数据）
class VentiTaskResponse(VentiTaskBase):
    id: int = Field(..., description="主键 ID")
    # nullable=True 对应 Optional[datetime] = None
    create_time: Optional[datetime] = Field(None, description="创建时间")
    update_time: Optional[datetime] = Field(None, description="更新时间")

    # 🚀 核心关键：开启从 ORM 属性中直接加载的功能（Pydantic v2 标准）
    model_config = {
        "from_attributes": True
    }


        