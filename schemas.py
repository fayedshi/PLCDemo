from pydantic import BaseModel, Field
from typing import Optional

# 🟢 基础模型（共用属性）
class GranaryBase(BaseModel):
    code: str = Field(..., example="AJ-001")
    name: str = Field(..., example="1号仓北廒间")
    capacity: int = Field(..., ge=1, example=3500)
    keeper: str = Field(..., example="张利国")
    grain_type: str = Field(..., example="小麦")
    max_temp: float = Field(..., example=22.0)

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
		