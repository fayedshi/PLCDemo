from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Float
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
    plc_code = Column(String(30), nullable=False, comment="PLCb编号")



class AlarmLog(Base):
    __tablename__ = "alarm_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(50), nullable=False)
    house_code = Column(String(50), nullable=False, index=True)
    message = Column(String(500), nullable=False)
    trigger_time = Column(DateTime, nullable=False)
    ack = Column(Boolean, nullable=False)
    ack_time=Column(DateTime, nullable=True)
    cleared= Column(Boolean, nullable=False)
    clear_time= Column(DateTime, nullable=True)
from sqlalchemy import String, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 1. 定义基础类（SQLAlchemy 2.0 推荐做法）
# class Base(DeclarativeBase):
#     pass


# 2. 定义通风模式模型
class VentilationMode(Base):
    __tablename__ = "ventilation_modes"

    # 主键 ID
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # 模式名称（不允许为空，且唯一）
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="模式名称")
    
    # 起始温差与湿度差
    start_temp_diff: Mapped[float] = mapped_column(Float, nullable=False, comment="起始温差")
    start_humidity_diff: Mapped[float] = mapped_column(Float, nullable=False, comment="起始湿度差")
    
    # 结束温差与湿度差
    end_temp_diff: Mapped[float] = mapped_column(Float, nullable=False, comment="结束温差")
    end_humidity_diff: Mapped[float] = mapped_column(Float, nullable=False, comment="结束湿度差")

    def __repr__(self) -> str:
        return f"<VentilationMode(name={self.name!r}, start_temp_diff={self.start_temp_diff})>"
