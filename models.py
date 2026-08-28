
from sqlalchemy import Column, Integer, String, Float
from database import Base

class Granary(Base):
    __tablename__ = "granary"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(50), unique=True, index=True, nullable=False, comment="廒间编号")
    name = Column(String(100), nullable=False, comment="廒间名称")
    capacity = Column(Integer, nullable=False, comment="设计仓容(吨)")
    keeper = Column(String(50), nullable=False, comment="保管员")
    grain_type = Column(String(50), nullable=False, comment="储粮品种")
    max_temp = Column(Float, nullable=False, comment="警报温度上限")
