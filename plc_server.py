import argparse
import os

from dotenv import load_dotenv
import uvicorn
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from pymodbus.client import AsyncModbusTcpClient
from contextlib import asynccontextmanager
import httpx
from models import AlarmLog
from schemas import AlarmLogCreate
from util import  build_influx_line_protocol, registers_to_val
from datetime import datetime
from database import AsyncSessionLocal, Base, engine
from routers.user_requests import router as user_request_router
from routers.gran_router import read_granaries, router as gran_router

# 设置日志级别为 DEBUG，并自定义格式
# logging.basicConfig(
#     level=logging.error,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )

# logging.info('这是一条基础信息日志')

# ==================== 1. 全局变量 ====================
# 全局共享的 PLC 最新数据缓存（所有手机都来这里拿数据，不直接轰炸 PLC）

plc_client = None

DATABASE_NAME='my_db'
STORAGE_INTERVAL=300

# HOUSE_CODE=None

# 1. 解析参数并加载环境（必须在最外层）
parser = argparse.ArgumentParser()
parser.add_argument('--env', choices=['dev', 'test'], default='dev')
parser.add_argument('--house-code', help="粮仓代码 (必填)")
args, _ = parser.parse_known_args()
if not args.house_code:
    # 使用 parser.error 会打印错误信息、显示帮助文档并自动执行 sys.exit(2) 退出
    parser.error("缺少必填参数: --house-code")

HOUSE_CODE = args.house_code

load_dotenv(dotenv_path=f".env.{args.env}")

# todo: 写在配置文件里
# dev_start_address={'win':1,'door':11,'fan':19,'exhaust':27,'ac':33}

plc_lock = asyncio.Lock()
window_state = {"status": "stopped"}

# active_alarms = {}
# app.state.TEMP_UPPER_LIMIT=None

# 最多读取120个寄存器
async def partial_read(start_address, cnt):
    async with plc_lock:
        result = await plc_client.read_holding_registers(address=start_address, count=cnt, device_id=1)
    if not result.isError():
        # print(f"【采集成功】温度数据: {result.registers} | 时间: {datetime.now()}")
        return result.registers
    else:
        raise Exception("【采集温度数据失败】PLC 内部错误响应")


@asynccontextmanager
async def lifespan(app: FastAPI):
    
    app.state.plc_ip= os.getenv("PLC_IP", "127.0.0.1")
    app.state.plc_port=os.getenv("PLC_PORT")
    print(f'读取plc IP: {app.state.plc_ip}, 端口{app.state.plc_port}')
    app.state.influx_db_url=os.getenv("INFLUX_DB_URL")
    app.state.influx_token=os.getenv("INFLUX_TOKEN")

    app.state.store_interval = 1

    app.state.global_plc_cache = []
    app.state.global_display_temp_cache = []

    app.state.global_humid_cache=[]
    app.state.global_power_cache=[]

    # alarms
    app.state.active_alarms={}
    app.state.partial_read=partial_read
    app.state.write_single_reg=write_single_reg
    async with engine.begin() as conn:
        # 如果表不存在，则自动创建（生产环境建议使用 Alembic 迁移）
        await conn.run_sync(Base.metadata.create_all)

    print("connected to mysql")
    print("\n--- 📊 当前环境配置变量 ---")
    print(f"后端服务 (influx_DB_URL): {app.state.influx_db_url}")

    # 全局初始化一次异步客户端
    global plc_client
    # global app.state.TEMP_UPPER_LIMIT
    try:
        
        plc_client = AsyncModbusTcpClient(app.state.plc_ip, port=app.state.plc_port, 
            reconnect_delay=1.0,
            reconnect_delay_max=120 
        )
        print("【系统启动】正在尝试与 PLC 建立唯一的长连接...")
        await plc_client.connect()
        print("【lifespan】物理通道已建立")
        granaries= await read_granary_conf()
        if granaries:
            app.state.TEMP_UPPER_LIMIT=granaries[0].max_temp
            print(f' temp upper limit {app.state.TEMP_UPPER_LIMIT}')
        else:
            raise Exception('【ERROR：无法读取仓房温度上限】')
        polling_job=asyncio.create_task(plc_polling_task())
        yield

    finally:
        # 关闭：断开 PLC 连接
        print("正在断开 PLC 连接...")
        polling_job.cancel()

        try:
            await asyncio.gather(polling_job)
        except asyncio.CancelledError:# interupted exception
            pass
        plc_client.close()
        print("###采集任务已停止，与PLC的连接已释放完毕")

app = FastAPI(lifespan=lifespan)
app.include_router(user_request_router, tags=["用户请求管理"])
app.include_router(gran_router, tags=["仓房管理"])


# 1. 解决跨域问题（允许 Vue 前端和手机端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 生产环境建议指定具体 IP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
async def read_granary_conf():
    async with AsyncSessionLocal() as session:
        granaries = await read_granaries(
            code = "001", 
            name=None,
            grain_type=None, 
            keeper=None, 
            db = session
        )
        print(f"【系统启动】读取到粮仓数据共 {len(granaries)} 条")
        return granaries

    
async def plc_polling_task():
    """该任务在后台独立运行，有且仅有它一个人维持与 PLC 的长连接"""
    # global global_plc_cache, global_display_temp_cache, global_humid_cache
    # HOUSE_CODE='001'
    while True:
        if not plc_client.connected:
            print("【连接断开，等待自动重连】")
            await asyncio.sleep(3)
            # 断开三次以上才记录alarm

            alarm_data = {
                "house_code": HOUSE_CODE,
                "type": "PLC_DISCONNECT",
                "message": f"❌ 通信故障：{HOUSE_CODE} PLC 连接断开！",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            gen_alarm('DISCONNECT',alarm_data)
            continue
        try:
            await remove_alarm(f"{HOUSE_CODE}__PLC_DISCONNECT")
            app.state.store_interval += 1
            await asyncio.gather(
                poll_and_store_temp(),
                poll_and_store_humid(),
                poll_and_store_power()
                
            )
            
        except Exception as e:
            print(f"【采集异常】: {e}, {datetime.now()}")
        finally:
            if app.state.store_interval==STORAGE_INTERVAL:
                app.state.store_interval=1
        # 每1秒采集一次
        await asyncio.sleep(1)


def check_cache_val(data_cache):
    for v in data_cache:
        if v >= 50000:
            print(f"***************** Invalid value found: {v},时间: {datetime.now()}")
            return False
        
    return True

async def check_temp(event_type, data_cache):
    curr_max_temp = round(max(data_cache)/10,1)
    # HOUSE_CODE='001'
    temp_key = f"{HOUSE_CODE}_{event_type}"
    
    # print('current max temperature: ',curr_max_temp,' limit ',app.state.TEMP_UPPER_LIMIT)
    if curr_max_temp >= app.state.TEMP_UPPER_LIMIT:
        alarm_data = {
            # "event": "ALARM_TRIGGER",
            "type": event_type,
            "house_code": HOUSE_CODE,
            "message": f"🔥 温度超限：{HOUSE_CODE} 当前温度 {curr_max_temp}℃ 超过设定的 {app.state.TEMP_UPPER_LIMIT}℃！",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        # app.state.active_alarms[temp_key]= alarm_data
         
        #  已经存在的话，就不去更新，保留第一条alarm
        if not app.state.active_alarms[temp_key]:
            await gen_alarm(temp_key,alarm_data)
            # todo: 
            await save_to_history_db(alarm_data)
    elif app.state.TEMP_UPPER_LIMIT - curr_max_temp >=0.5:
        # 当前温度小于阈值 0.5°的回查以上才消除警报
        await gen_alarm(temp_key,{})
        # await remove_alarm(temp_key)

async def save_to_history_db(alarm_data: dict):
    # 1. 使用 Pydantic 进行第一轮严格的数据校验和清洗
    try:
        validated_data = AlarmLogCreate(**alarm_data)
    except Exception as e:
        print(f"❌ 报警数据格式校验失败: {e}")
        return

    # 2. 数据库会话上下文管理
    # db = SessionLocal()
    async with AsyncSessionLocal() as session:
        try:
            # 3. 将校验通过的数据转化为 SQLAlchemy 的模型实例
            # model_dump() 会把 Pydantic 对象变回 Python 字典（老版本 Pydantic 请用 .dict()）
            db_alarm = AlarmLog(**validated_data.model_dump())
            
            # 4. 执行插入并提交
            session.add(db_alarm)
            session.commit()
            session.refresh(db_alarm)
            print(f"💾 报警记录已成功持久化到 MySQL，自增 ID: {db_alarm.id}")
        except Exception as e:
            session.rollback()  # 发生异常立即回滚
            print(f"❌ 报警入库失败，已自动回滚: {e}")

async def gen_alarm(alarm_key,alarm_data):
    app.state.active_alarms[alarm_key]= alarm_data
 

async def remove_alarm(alarm_key):
    app.state.active_alarms.pop(alarm_key, None)



async def poll_and_store_temp():
    try:
        temp_data=await partial_read(35,120)
        # print(f"【采集成功】温度数据: {global_plc_cache[0]} | 时间: {datetime.now()}")
        # break
        temp_data.extend(await partial_read(155,20))
        # 临时加入，检查异常值，可能不需要
        res =  check_cache_val(temp_data)
        if not res:
            print(f"*****************PLC内部异常 in poll_and_store_temp: ，等待2分钟")
            await asyncio.sleep(120)
            return

        await check_temp('TEMP_HIGH', temp_data)
        app.state.global_plc_cache = temp_data
        temp_data = [round(x / 10, 1) for x in temp_data]
        app.state.global_display_temp_cache=temp_data
        
        if app.state.store_interval==STORAGE_INTERVAL:
            await prep_store_data_cache(app.state.global_plc_cache, 'plc_temp_data','temp')
            print(f'【温度数据存储成功】{datetime.now()}')
    except Exception as e:
        print(f'############## poll_and_store_temp 发生异常: {e}, {datetime.now()}')


async def poll_and_store_humid():
    try:
        # 读取140个湿度数据
        humid_cache=await partial_read(175,120)
        humid_cache.extend(await partial_read(195,20))
        if not check_cache_val(humid_cache):
            print(f"*****************PLC内部异常 in poll_and_store_humid: ，等待2分钟")
            await asyncio.sleep(120)
            return
        app.state.global_humid_cache=humid_cache
        if app.state.store_interval==STORAGE_INTERVAL:
            await prep_store_data_cache(app.state.global_humid_cache, 'plc_humid_data','humid')
            print(f'【湿度数据存储成功】{datetime.now()}')
    except Exception as e:
        print(f'############## poll_and_store_humid 发生异常: {e}, {datetime.now()}')

async def poll_and_store_power():
    try:
        raw_regs=await partial_read(405,10)
        data = []
        # 每次跳 2 步
        for i in range(0, len(raw_regs), 2):
            # pair = data[i:i+2]
            
            if i==len(raw_regs)-2:
                # print(f'power data regs: {raw_regs[i]},{raw_regs[i+1]}')
                consumEnerg=round(registers_to_val(raw_regs[i],raw_regs[i+1],'I')/1000,1)
                data.append(consumEnerg)
            else:
                data.append(round(registers_to_val(raw_regs[i],raw_regs[1+1],'f'),1))
        
        app.state.global_power_cache = data
        if app.state.store_interval == STORAGE_INTERVAL:
            print('done power read ',data)
            await prep_store_data_cache(app.state.global_power_cache, 'plc_power_data','power')
            print(f'【功率数据存储成功】{datetime.now()}')
    except Exception as e:
        print(f'############## poll_and_store_power 发生异常: {e}, {datetime.now()}')

async def prep_store_data_cache(data_cache, table, field_prefix):
    try:
        plc_channels={}
        for i in range(0, len(data_cache)):
            plc_channels[f"{field_prefix}{i}"] = data_cache[i]
            # print(global_plc_cache[i])
        device_tags = {
            "plc_type": "s7-smart200",
            "station_id": "line_01"
        }

        # 动态生成 len(data_cache) 个字段的行协议数据,如果这步发生异常，就直接catch，不往下走，所以build_influx_line_protocol中
        # 需要抛出异常
        influx_data_line = await build_influx_line_protocol(
            measurement = table, 
            tags = device_tags, 
            fields=plc_channels
        )
        print(f'拼接后的字符串： {influx_data_line}')
        await send_to_influx(influx_data_line)
        
    except Exception as e:
        raise Exception(f'##############prep_store_data_cache 发生异常: {e}')


async def send_to_influx(payload_text: str):
    """
    底层的异步发送函数，向 InfluxDB 发送 HTTP POST 请求
    """
    headers = {
        "Authorization": f"Token {app.state.influx_token}",
        "Content-Type": "text/plain; charset=utf-8"
    }
    WRITE_URL = f"{app.state.influx_db_url}/api/v3/write_lp?db={DATABASE_NAME}&precision=ns"

    # 使用 httpx.AsyncClient 建立异步 HTTP 客户端
    async with httpx.AsyncClient() as client:
        try:
            # content 参数接收纯文本的行协议数据（多行用 \n 分割）
            response = await client.post(WRITE_URL, headers=headers, content=payload_text, timeout=10.0)
            
            # InfluxDB 3 写入成功时通常返回 204 No Content
            if response.status_code == 204:
                print(f"[成功] 成功异步写入数据块，大小: {len(payload_text.splitlines())} 行，时间: {datetime.now()}")
            else:
                raise Exception(f"[错误] 写入失败，状态码: {response.status_code}, 原因: {response.text} {datetime.now()}")
        except Exception as e:
            raise Exception(f"[异常] 异步发送过程中发生错误，{datetime.now()}: {e} ")

async def write_single_reg(start_add: int, val:int):
    async with plc_lock:
        response = await plc_client.write_register(address=start_add, value=val, device_id=1, no_response_expected=False)
    if response.isError():
        print("写入异常")
    else:
        print("写入成功，当前寄存器值:", response)        

if __name__ == "__main__":
    # 核心：启动内置 Web 容器，监听 0.0.0.0 允许局域网（手机）访问
    uvicorn.run("plc_server:app", host="0.0.0.0", port=8000, reload=True)