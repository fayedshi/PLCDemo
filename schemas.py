from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


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
    type: str = Field(..., description="报警类型", example="TEMP_HIGH")
    house_code: str = Field(..., description="粮仓代码", example="001")
    message: str = Field(..., description="报警消息文本")

class AlarmLogCreate(AlarmLogBase):
    """
    专用于插入/创建时的 Schema
    """
    # 💡 兼容处理：允许传入纯文本字符串时间（如 "2026-09-09 17:51:00"）或 datetime 对象
    time: Optional[datetime] = Field(default_factory=datetime.now, description="报警时间")

class AlarmLogResponse(AlarmLogBase):
    """
    专用于从数据库查询出来、返回给 Vue 前端时的 Schema
    """
    id: int
    time: datetime

    class Config:
        # 💡 必须开启：允许 Pydantic 自动解析 SQLAlchemy 的 ORM 对象
        from_attributes = True  # 在老版本 Pydantic 中是 orm_mode = True