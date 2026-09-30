from datetime import datetime
from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, SmallInteger, String, Float
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

# 2. 定义通风模式模型
class VentiTask(Base):
    __tablename__ = "ventilation_jobs"

    # 主键 ID
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # 模式名称（不允许为空，且唯 一） 
    house_code: Mapped[str] = mapped_column(String(10), nullable=False,  comment="仓房代码")
    mode_id: Mapped[int] = mapped_column(Integer, nullable=True, comment="模式ID")
    mode_name: Mapped[str] = mapped_column(String(50), nullable=True, comment="模式名称")
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, comment="状态代码")
    status_text: Mapped[str] = mapped_column(String(50), nullable=False, comment="状态信息")
    create_time= Column(DateTime, nullable=True)
    update_time= Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<VentiTask(name={self.mode_name!r}, status_code={self.status_code})>"


class CAModuleModel(Base):
    __tablename__ = "ca_module_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # 核心气调参数 (14个基础字段)
    mode_name = Column(String(50), nullable=False, comment="模式名称")
    target_warehouse_pressure = Column(Float, default=0.0, comment="目标仓压值")
    nitrogen_fill_amount = Column(Float, default=0.0, comment="充氮量值")
    exhaust_time = Column(Integer, default=0, comment="排气时间(秒)")
    waste_nitrogen_concentration = Column(Float, default=0.0, comment="废氮浓度值")
    evacuation_negative_pressure = Column(Float, default=0.0, comment="抽空负压值")
    target_concentration = Column(Float, default=0.0, comment="目标浓度值")
    auto_concentration_hold = Column(Float, default=0.0, comment="自动浓度保持值")
    ab_group_concentration_diff = Column(Float, default=0.0, comment="AB组浓度差")
    waste_nitrogen_utilization_interval = Column(Integer, default=0, comment="废氮利用间隔(分钟)")
    maintain_negative_pressure = Column(Float, default=0.0, comment="维持负压值")
    pause_warehouse_pressure = Column(Float, default=0.0, comment="暂停仓压值")
    circulation_time = Column(Integer, default=0, comment="环流时间(秒)")
    evacuation_pressure = Column(Float, default=0.0, comment="抽空压力值")
    
    # 26个阀门对应的字段 (Boolean 代表开关状态，或者用 Integer 代表开度)
    # 动态生成字段定义，保持代码整洁
    for i in range(1, 27):
        locals()[f"valve_{i}"] = Column(Boolean, default=False, comment=f"{i}号阀门状态")

    for i in range(1, 7):
            locals()[f"blower_{i}"] = Column(Boolean, default=False, comment=f"{i}号风机状态")
            
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class CAJobModel(Base):
    __tablename__ = "ca_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    house_code = Column(String(50), nullable=False, index=True, comment="仓房编号")
    mode_id = Column(Integer, nullable=False, comment="关联的气调模式ID")
    mode_name = Column(String(50), nullable=False, comment="模式名称")
    
    # 核心状态控制：0-等待触发, 1-运行中, 2-已暂停, 3-正常结束, 4-被人为中止, 5-异常中止
    status_code = Column(SmallInteger, default=0, index=True)
    status_text = Column(String(20), default="等待触发")
    
    plan_start_time = Column(DateTime, nullable=True, comment="计划开始时间")
    start_time = Column(DateTime, nullable=True, comment="实际开始时间")
    end_time = Column(DateTime, nullable=True, comment="结束/中止时间")
    
    # 镜像保存当时的快照参数（防止配置表被修改后影响历史追溯）
    runtime_params = Column(JSON, nullable=True, comment="运行时的完整工艺与阀门参数快照")
    
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)




