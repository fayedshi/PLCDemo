import uvicorn
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from pymodbus.client import AsyncModbusTcpClient
from contextlib import asynccontextmanager
import httpx
from config import settings
from log.plc_logger import get_logger
from models import AlarmLog
from schemas import AlarmLogCreate
from util import  build_influx_line_protocol, registers_to_val
from datetime import datetime
from database import AsyncSessionLocal, Base, engine
from routers.user_requests import router as user_request_router
from routers.venti_router import router as venti_router
from routers.gran_router import read_granaries, router as gran_router
from config_loader import load_config

# ==================== 1. 全局变量 ====================
# 全局共享的 PLC 最新数据缓存（所有手机都来这里拿数据，不直接轰炸 PLC）

DATABASE_NAME='my_db'
STORAGE_INTERVAL=300
GLOBAL_POLLING_INTERVAL=300
GLOBAL_STORE_INTERVAL=300
# 1. 解析参数并加载环境（必须在最外层）
# parser = argparse.ArgumentParser()
# parser.add_argument('--env', choices=['dev', 'test'], default='dev')
# parser.add_argument('--house-code', help="粮仓代码 (必填)")
# args, _ = parser.parse_known_args()
# if not args.house_code:
#     # 使用 parser.error 会打印错误信息、显示帮助文档并自动执行 sys.exit(2) 退出
#     parser.error("缺少必填参数: --house-code")

# HOUSE_CODE = args.house_code

# load_dotenv(dotenv_path=f".env.{args.env}")

# todo: 写在配置文件里
# dev_start_address={'win':1,'door':11,'fan':19,'exhaust':27,'ac':33}



plc_lock = asyncio.Lock()
window_state = {"status": "stopped"}
logger=None
config_data=settings.raw_config
# granaries = config_data.get('granaries', [])
granaries= settings.granaries
silos_cnt=len(granaries)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global logger
    logger=get_logger()

    # app.state.plc_ip= os.getenv("PLC_IP", "127.0.0.1")
    # app.state.plc_port=os.getenv("PLC_PORT")
    logger.info(f'silo_cnt: {silos_cnt}')
    
    app.state.num_ticks = [1] * silos_cnt
    app.state.dev_addrs_objects=[]
    app.state.global_plc_cache = [[] for _ in range(silos_cnt)]
    app.state.global_display_temp_cache = [[] for _ in range(silos_cnt)]

    app.state.global_humid_cache=[[] for _ in range(silos_cnt)]
    app.state.global_power_cache=[[] for _ in range(silos_cnt)] 
    # intitialize limit array with max_temp as 100 degree
    app.state.TEMP_UPPER_LIMIT_LIST = [100] * silos_cnt

    # alarms
    app.state.active_alarms={}
    app.state.partial_read=partial_read
    app.state.write_single_reg=write_single_reg
    # app.state.check_temp_alarm=check_temp_alarm

    app.state.influx_db_url=config_data["INFLUX_DB"]['URL']
    app.state.influx_token=config_data["INFLUX_DB"]["TOKEN"]
    
    # customize polling frequency in different cases
    app.state.read_temp_humid_interval={}
    # {house_code, read_temp_humid_interval=30}, base once/1min,  5s for live 

    app.state.read_alarm_interval=5
    # {house_code, read_alarm_interval}, base once/2 min,  2s for live 
    app.state.read_power_interval={}
    app.state.read_dev_state_interval={}
    # {house_code, read_dev_state_interval}, base once/5 min,  1s for live 
    
    app.state.plc_conns=[]
    for i in range(silos_cnt):
        app.state.read_temp_humid_interval[i]= 100
        app.state.read_power_interval[i]=300
        # app.state.read_alarm_interval[i]=100
        app.state.read_dev_state_interval[i]=300
    
    logger.info(f'read granaries: {granaries}')

    async with engine.begin() as conn:
        # 如果表不存在，则自动创建（生产环境建议使用 Alembic 迁移）
        await conn.run_sync(Base.metadata.create_all)

    logger.info("connected to mysql")
    logger.info("\n--- 📊 当前环境配置变量 ---")
    logger.info(f"后端服务 (influx_DB_URL): {app.state.influx_db_url}")

    try:
        polling_tasks=[]
        # plc_clients=[]
        for index, gran in enumerate(granaries):
            plc_client = AsyncModbusTcpClient(gran['PLC_IP'], port=gran['PLC_PORT'], 
                reconnect_delay=1.0,
                reconnect_delay_max=120 
            )
            logger.info("【系统启动】正在尝试与 PLC 建立唯一的长连接...")
            await plc_client.connect()
            logger.info("【lifespan】物理通道已建立")

            app.state.plc_conns.append(plc_client)
            logger.info(f'index: {index}')
            app.state.num_ticks[index]=1
            # 从数据库中读取该仓房的温度报警上限
            gran_list= await read_granary_max_temp(gran['code'])
            if gran_list:
                app.state.TEMP_UPPER_LIMIT_LIST[index] = gran_list[0].max_temp
                logger.info(f'temp upper limit {app.state.TEMP_UPPER_LIMIT_LIST[index]}')
            else:
                raise Exception('【ERROR：无法读取仓房温度上限】')
            
            # 从配置文件中读取设备地址
            # dev_addrs = load_device_addr()
            logger.info(f'current gran {gran}')
            logger.info(f'gran _devices_addr, {gran["devices_addr"]}')
            app.state.dev_addrs_objects.append(gran['devices_addr'])
            logger.info(app.state.dev_addrs_objects)
            temp_start=gran['devices_addr']['temp']
            # polling_job = asyncio.create_task(plc_polling_task(index, plc_client, gran['code']))
            task_check_plc_connection=asyncio.create_task(check_plc_connection(index, plc_client, gran['code']))

            task_read_temp=asyncio.create_task(read_temp(index, plc_client, gran['code']))
            task_check_alarm =asyncio.create_task(check_temp_alarm('TEMP_HIGH', gran['code'], index))
            # task_store_temp=asyncio.create_task(store_temp(index, gran['code']))

            # task_read_humid=asyncio.create_task(read_humid(index, plc_client, gran['code']))
            # task_store_humid=asyncio.create_task(store_humid(index, gran['code']))
            
            # task_read_power=asyncio.create_task(read_power(index, plc_client, gran['code']))
            # task_store_power=asyncio.create_task(store_power(index, gran['code']))

            polling_tasks.extend([task_check_plc_connection, task_read_temp, task_check_alarm, 
                                #   task_store_temp ,
                                #   task_read_humid, task_store_humid, 
                                #     task_read_power, task_store_power
                                    ]) 
        yield

    finally:
        logger.info("正在断开 所有PLC 连接...")
        for task in polling_tasks:
            task.cancel()

        try:
            await asyncio.gather(*polling_tasks)
        except asyncio.CancelledError:# interupted exception
            pass
        for plc_client in app.state.plc_conns:
            plc_client.close()
            logger.info(f"###{plc_client}采集任务已停止，与PLC的连接已释放完毕")

app = FastAPI(lifespan=lifespan)
app.include_router(user_request_router, tags=["用户请求管理"])
app.include_router(gran_router, tags=["仓房管理"])
app.include_router(venti_router, tags=["venti-mode config"])


# 1. 解决跨域问题（允许 Vue 前端和手机端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 生产环境建议指定具体 IP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# def register_glob_vars(app: FastAPI):


# def load_device_addr():
#     logger.info('to load yaml')
#     # with open(f'{args.env}.yaml', 'r', encoding='utf-8') as file:
#     #     # 2. 使用 yaml.safe_load 读取文件内容
#     #     config_data = yaml.safe_load(file)
#     # config_data = load_config(args.env)
#     granaries = config_data.get('granaries', [])
#     for item in granaries:
#         if item.get('code') == HOUSE_CODE:
#             return item.get('devices_addr')
#     return None
        # print(config_data['granaries'][0])  # 输出: localhost



# active_alarms = {}
# app.state.TEMP_UPPER_LIMIT=None

# 最多读取120个寄存器
async def partial_read(plc_client, start_address, cnt):
    async with plc_lock:
        result = await plc_client.read_holding_registers(address=start_address, count=cnt, device_id=1)
    if not result.isError():
        # logger.info(f"【采集成功】温度数据: {result.registers} | 时间: {datetime.now()}")
        return result.registers
    else:
        raise Exception("【采集温度数据失败】PLC 内部错误响应")


async def read_granary_max_temp(gran_code):
    async with AsyncSessionLocal() as session:
        granaries = await read_granaries(
            code = gran_code, 
            name=None,
            grain_type=None, 
            keeper=None, 
            db = session
        )
        logger.info(f"【系统启动】读取到粮仓数据共 {len(granaries)} 条")
        return granaries

    
# async def plc_polling_task(index, plc_client, house_code):
#     """该任务在后台独立运行，有且仅有它一个人维持与 PLC 的长连接"""
#     event_type='PLC_DISCONNECT'
#     while True:
#         if not plc_client.connected:
#             logger.error("【连接断开，等待自动重连】")
#             await asyncio.sleep(3)
#             # todo: 断开三次以上才记录alarm
#             msg=f"❌ 通信故障：{house_code} PLC 连接断开！"
#             # alarm_data = create_alarm_json(event_type, HOUSE_CODE, f"❌ 通信故障：{HOUSE_CODE} PLC 连接断开！")
#             # if not app.state.active_alarms[alarm_key]:
#             # gen_alarm(alarm_key, alarm_data)
#             await gen_alarm(event_type, house_code, msg)
#             logger.info('after gen_alarm for plc')
#             continue
#         try:
#             await clear_alarm(event_type, house_code)
#             app.state.num_ticks[index] += 1
#             await asyncio.gather(
#                 process_temp(index, plc_client, house_code),
#                 process_humid(index, plc_client, house_code),
#                 process_power(index, plc_client, house_code),
#                 # todo: collect devices states
#                 # process_dev_state(plc_client, house_code),   
#             )
            
#         except Exception as e:
#             logger.info(f"【采集异常】: {e}, {datetime.now()}")
#         finally:
#             if app.state.num_ticks[index]==STORAGE_INTERVAL:
#                 app.state.num_ticks[index] = 1
#         # 每1秒采集一次
#         await asyncio.sleep(1)

async def check_plc_connection(index, plc_client, house_code):
    """该任务在后台独立运行，有且仅有它一个人维持与 PLC 的长连接"""
    logger.info('in check_plc_connection')
    event_type='PLC_DISCONNECT'
    while True:
        if not plc_client.connected:
            logger.error("【连接断开，等待自动重连】")
            await asyncio.sleep(3)
            # todo: 断开三次以上才记录alarm
            msg=f"❌ 通信故障：{house_code} PLC 连接断开！"
            await gen_alarm(event_type, house_code, msg)
            logger.info('after gen_alarm for plc')
            continue
        try:
            await clear_alarm(event_type, house_code)            
        except Exception as e:
            logger.info(f"【PLC连接异常】: {e}, {datetime.now()}")
        
        # 每1秒采集一次
        await asyncio.sleep(GLOBAL_POLLING_INTERVAL)

# process_temp_new:

# async def is_live_action:
#     if live_read:
        

def check_cache_val(data_cache):
    for v in data_cache:
        if v >= 50000:
            logger.info(f"***************** Invalid value found: {v},时间: {datetime.now()}")
            return False
        
    return True

# UNACK_ACTIVE(未确未复), ACK_ACTIVE(已确未复), UNACK_CLEAR(未确已复)
async def check_temp_alarm(event_type, house_code,index):
    logger.info('in check_temp_alarm')
    while(True):
        if not app.state.global_plc_cache[index]:
            await asyncio.sleep(2)
        # if app.state.num_ticks[index] % app.state.read_alarm_interval[index]:
        #     return
        curr_max_temp = round(max(app.state.global_plc_cache[index])/10,1)
        # logger.info(f'current max temperature: {curr_max_temp}, limit: {app.state.TEMP_UPPER_LIMIT_LIST[index]}')
        if curr_max_temp >= app.state.TEMP_UPPER_LIMIT_LIST[index]:
            #  已经存在的话，就不去更新，保留第一条alarm
            # if temp_key not in app.state.active_alarms or not app.state.active_alarms[temp_key]:
            msg = f"🔥 温度超限：house-{house_code} 当前温度 {curr_max_temp}℃ 超过设定的 {app.state.TEMP_UPPER_LIMIT_LIST[index]}℃！"
            # logger.info('to generate alarm')
            await gen_alarm(event_type, house_code, msg)
        # 当前温度小于阈值 0.5°的回差以上才消除警报
        elif app.state.TEMP_UPPER_LIMIT_LIST[index] - curr_max_temp >=0.5:
            # logger.info('going to clear alarm')
            await clear_alarm(event_type, house_code)
        await asyncio.sleep(app.state.read_alarm_interval)
            
async def clear_alarm(event_type, house_code):
    alarm_key = f"{house_code}_{event_type}"
    # logger.info(f'in clear_alarm(), alarm_key: {alarm_key}')
    if alarm_key in app.state.active_alarms and app.state.active_alarms[alarm_key]:
        logger.info('##To clear alarm ',app.state.active_alarms[alarm_key])
        # 已经存在 {alarm_key: {}}, no more update to the empty alarm
        alarm_data = app.state.active_alarms[alarm_key]
        alarm_data['cleared'] = True
        alarm_data['clear_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if alarm_data['ack']:
            # 将警报置空
            app.state.active_alarms[alarm_key]= {}
            # 同时已确认和已消除，才进history
            logger.info(f'准备消除alarm，并存入历史报警,{alarm_key}')
            await save_to_history_db(alarm_data)

def create_alarm_json(event_type, HOUSE_CODE, msg):
    return {
        # "event": "ALARM_TRIGGER",
        "type": event_type,
        "house_code": HOUSE_CODE,
        "message": msg,
        "trigger_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "clear_time": None,
        "ack": False,
        "ack_time": None,
        "cleared": False
    }

async def save_to_history_db(alarm_data: dict):
    # 1. 使用 Pydantic 进行第一轮严格的数据校验和清洗
    try:
        validated_data = AlarmLogCreate(**alarm_data)
    except Exception as e:
        logger.info(f"❌ 报警数据格式校验失败: {e}")
        return

    # 2. 数据库会话上下文管理
    async with AsyncSessionLocal() as session:
        try:
            logger.info('in AsyncSessionLocal: ',AsyncSessionLocal)
            # 3. 将校验通过的数据转化为 SQLAlchemy 的模型实例
            # model_dump() 会把 Pydantic 对象变回 Python 字典（老版本 Pydantic 请用 .dict()）
            db_alarm = AlarmLog(**validated_data.model_dump())
            logger.info('db_alarm',db_alarm)
            # 4. 执行插入并提交
            session.add(db_alarm)
            await session.commit()
            # await session.refresh(db_alarm)
            logger.info(f"💾 报警记录已成功持久化到 MySQL，自增 ID: {db_alarm.id}")
        except Exception as e:
            await session.rollback()
            logger.info(f"❌ 报警入库失败，已自动回滚: {e}")

async def gen_alarm(event_type, house_code, msg):
    logger.info(f'in gen_alarm {msg}')
    alarm_key = f"{house_code}_{event_type}"
    if alarm_key not in app.state.active_alarms or not app.state.active_alarms[alarm_key]:
        logger.info(f'======> No existing temp alarm in house-{house_code}, generating... ')
        alarm_data = create_alarm_json(event_type, house_code, msg)
        app.state.active_alarms[alarm_key]= alarm_data
 

# async def remove_alarm(alarm_key):
#     # app.state.active_alarms.pop(alarm_key, None)
#     app.state.active_alarms[alarm_key]= {}


async def read_temp_data(temp_start_addr, plc_client):
    temp_data=await partial_read(plc_client, temp_start_addr, 120)
    # logger.info(f"【采集成功】温度数据: {global_plc_cache[0]} | 时间: {datetime.now()}")
    # break
    temp_data.extend(await partial_read(plc_client,temp_start_addr+120,20))
    return temp_data



async def process_temp(index, plc_client, house_code, temp_start):
    while(True):
        try:
            logger.info('in process_temp')
            # temp_data=await partial_read(plc_client,35,120)
            # # logger.info(f"【采集成功】温度数据: {global_plc_cache[0]} | 时间: {datetime.now()}")
            # # break
            # temp_data.extend(await partial_read(plc_client,155,20))
            # 临时加入，检查异常值，可能不需要
            temp_data= await read_temp_data(temp_start, plc_client)
            res =  check_cache_val(temp_data)
            if not res:
                logger.info(f"*****************PLC内部异常 in poll_and_store_temp: ，等待1分钟")
                await asyncio.sleep(60)
                return

            # check alarm and format display data and store temp
            await asyncio.gather(
                check_temp_alarm('TEMP_HIGH', temp_data, house_code,index), 
                format_display_temp(index,temp_data), 
                store_temp(index,temp_data, house_code), return_exceptions=True)
        except Exception as e:
            logger.info(f'############## poll_and_store_temp in house-{house_code}发生异常: {e}, {datetime.now()}')
        await asyncio.sleep(GLOBAL_POLLING_INTERVAL)

async def read_temp(index, plc_client, house_code):
    while(True):
        try:
            temp_data=await partial_read(plc_client,35,120)
            # logger.info(f"【采集成功】温度数据: {global_plc_cache[0]} | 时间: {datetime.now()}")
            # break
            temp_data.extend(await partial_read(plc_client,155,20))
            # 临时加入，检查异常值，可能不需要
            # temp_data= await read_temp_data(temp_start, plc_client)
            # todo: 读取室外温度
            ext_temp_addr =granaries[index]['devices_addr']['ext-temp'][0]
            
            external_temp=await partial_read(plc_client,ext_temp_addr,1)

            res =  check_cache_val(temp_data)
            if not res:
                logger.info(f"*****************PLC内部异常 in poll_and_store_temp: ，等待1分钟")
                app.state.global_plc_cache[index]=[]
                await asyncio.sleep(60)
                return
            app.state.global_plc_cache[index] = temp_data
            temp_data = [round(x / 10, 1) for x in temp_data]
            app.state.global_display_temp_cache[index] = temp_data
            # format_display_temp(index,temp_data), 
        except Exception as e:
            logger.info(f'############## poll_and_store_temp in house-{house_code}发生异常: {e}, {datetime.now()}')
        await asyncio.sleep(GLOBAL_POLLING_INTERVAL)


async def format_display_temp(index,temp_data):
    # logger.info('after check_temp')
    # if app.state.num_ticks[index] % app.state.read_temp_humid_interval[index] == 0:
        app.state.global_plc_cache[index] = temp_data
        temp_data = [round(x / 10, 1) for x in temp_data]
        app.state.global_display_temp_cache[index] = temp_data

async def store_temp(index, house_code):
    while True:
        # if app.state.num_ticks[index]==STORAGE_INTERVAL:
        if not app.state.global_plc_cache[index]:
            logger.info('No data in temp cache, waiting for 2secs **********************')
            await asyncio.sleep(2)
        await prep_store_data_cache(app.state.global_plc_cache[index], house_code, 'plc_temp_data','temp')
        logger.info(f'【温度数据存储成功 house-{house_code}】{datetime.now()}')
        await asyncio.sleep(GLOBAL_STORE_INTERVAL)


async def store_humid(index, house_code):
    while True:
        if not app.state.global_humid_cache[index]:
            await asyncio.sleep(2)
        # if app.state.num_ticks[index]==STORAGE_INTERVAL:
        await prep_store_data_cache(app.state.global_humid_cache[index], house_code, 'plc_humid_data','humid')
        # await prep_store_data_cache(humid_cache, house_code, 'plc_humid_data','humid')
        logger.info(f'【Humidity数据存储成功 house-{house_code}】{datetime.now()}')
        await asyncio.sleep(GLOBAL_STORE_INTERVAL)

async def store_power(index,  house_code):
    while True:
        if(not app.state.global_power_cache[index]):
            await asyncio.sleep(2)  
        # if app.state.num_ticks[index]==STORAGE_INTERVAL:
        await prep_store_data_cache(app.state.global_power_cache[index], house_code, 'plc_power_data','power')
        # await prep_store_data_cache(humid_cache, house_code, 'plc_humid_data','humid')
        logger.info(f'【能耗数据存储成功 house-{house_code}】{datetime.now()}')
        await asyncio.sleep(GLOBAL_STORE_INTERVAL)

# await prep_store_data_cache(data, house_code, 'plc_power_data','power')
# async def process_humid(index, plc_client, house_code):
#     while True:
#         try:
#                 logger.info('in process_humid')
#             # if app.state.num_ticks[index] % app.state.read_temp_humid_interval[index] ==0:
#                 # 读取140个湿度数据
#                 humid_cache=await partial_read(plc_client, 175,120)
#                 humid_cache.extend(await partial_read(plc_client,195,20))
#                 if not check_cache_val(humid_cache):
#                     logger.info(f"*****************PLC内部异常 in poll_and_store_humid: ，等待1分钟")
#                     await asyncio.sleep(60)
#                     return
#                 app.state.global_humid_cache[index] = humid_cache

#             # if app.state.num_ticks[index]==STORAGE_INTERVAL:
#                 await prep_store_data_cache(humid_cache, house_code, 'plc_humid_data','humid')
#                 logger.info(f'【湿度数据存储成功】{datetime.now()}')
#         except Exception as e:
#             logger.info(f'############## poll_and_store_humid 发生异常: {e}, {datetime.now()}')
#         await asyncio.sleep(GLOBAL_POLLING_INTERVAL)

async def read_humid(index, plc_client, house_code):
    while True:
        try:
            logger.info('in process_humid')
        # if app.state.num_ticks[index] % app.state.read_temp_humid_interval[index] ==0:
            # 读取140个湿度数据
            humid_cache=await partial_read(plc_client, 175,120)
            humid_cache.extend(await partial_read(plc_client,195,20))
            if not check_cache_val(humid_cache):
                logger.info(f"*****************PLC内部异常 in poll_and_store_humid: ，等待1分钟")
                app.state.global_humid_cache[index]=[]
                await asyncio.sleep(60)
                return
            app.state.global_humid_cache[index] = humid_cache

        # if app.state.num_ticks[index]==STORAGE_INTERVAL:
            # await prep_store_data_cache(humid_cache, house_code, 'plc_humid_data','humid')
            # logger.info(f'【湿度数据存储成功】{datetime.now()}')
        except Exception as e:
            logger.info(f'############## poll_and_store_humid 发生异常: {e}, {datetime.now()}')
        await asyncio.sleep(GLOBAL_POLLING_INTERVAL)


# async def process_power(index, plc_client, house_code):
#     while True:
#         try:
#             logger.info('in process_power')
#             if app.state.num_ticks[index] % app.state.read_power_interval[index]==0:
#                 raw_regs=await partial_read(plc_client,405,10)
#                 data = []
#                 # 每次跳 2 步
#                 for i in range(0, len(raw_regs), 2):
#                     # pair = data[i:i+2]
#                     if i==len(raw_regs)-2:
#                         # logger.info(f'power data regs: {raw_regs[i]},{raw_regs[i+1]}')
#                         consumEnerg=round(registers_to_val(raw_regs[i],raw_regs[i+1],'I')/1000,1)
#                         data.append(consumEnerg)
#                     else:
#                         data.append(round(registers_to_val(raw_regs[i],raw_regs[1+1],'f'),1))
#                 app.state.global_power_cache[index] = data
            
#             # if app.state.num_ticks[index] == STORAGE_INTERVAL:
#                 # logger.info('done power read ',data)
#                 await prep_store_data_cache(data, house_code, 'plc_power_data','power')
#                 logger.info(f'【功耗数据存储成功】{datetime.now()}')
#         except Exception as e:
#             logger.error(f'############## poll_and_store_power 发生异常: {e}, {datetime.now()}')
#         await asyncio.sleep(GLOBAL_POLLING_INTERVAL)


async def read_power(index, plc_client, house_code):
    while True:
        try:
            logger.info('in read_power')
            # if app.state.num_ticks[index] % app.state.read_power_interval[index]==0:
            raw_regs=await partial_read(plc_client,405,10)
            data = []
            # 每次跳 2 步
            for i in range(0, len(raw_regs), 2):
                # pair = data[i:i+2]
                if i==len(raw_regs)-2:
                    # logger.info(f'power data regs: {raw_regs[i]},{raw_regs[i+1]}')
                    consumEnerg=round(registers_to_val(raw_regs[i],raw_regs[i+1],'I')/1000,1)
                    data.append(consumEnerg)
                else:
                    data.append(round(registers_to_val(raw_regs[i],raw_regs[1+1],'f'),1))
            app.state.global_power_cache[index] = data
        
        # if app.state.num_ticks[index] == STORAGE_INTERVAL:
            # logger.info('done power read ',data)
            # await prep_store_data_cache(data, house_code, 'plc_power_data','power')
            # logger.info(f'【功耗数据存储成功】{datetime.now()}')
        except Exception as e:
            logger.error(f'############## poll_and_store_power 发生异常: {e}, {datetime.now()}')
        await asyncio.sleep(GLOBAL_POLLING_INTERVAL)


async def prep_store_data_cache(data_cache, house_code, table, field_prefix):
    try:
        plc_channels={}
        for i in range(0, len(data_cache)):
            plc_channels[f"{field_prefix}{i}"] = data_cache[i]
            # logger.info(global_plc_cache[i])
        device_tags = {
            "plc_type": "s7-smart200",
            "station_id": house_code
        }

        # 动态生成 len(data_cache) 个字段的行协议数据,如果这步发生异常，就直接catch，不往下走，所以build_influx_line_protocol中
        # 需要抛出异常
        influx_data_line = await build_influx_line_protocol(
            measurement = table, 
            tags = device_tags, 
            fields=plc_channels
        )
        logger.info(f'拼接后的字符串 for 仓房-{house_code}: {influx_data_line}')
        await send_to_influx(influx_data_line)
        
    except Exception as e:
        raise Exception(f'##############prep_store_data_cache house-{house_code} 发生异常: {e}')


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
                logger.info(f"[成功] 成功异步写入数据块，大小: {len(payload_text.splitlines())} 行，时间: {datetime.now()}")
            else:
                raise Exception(f"[错误] 写入失败，状态码: {response.status_code}, 原因: {response.text} {datetime.now()}")
        except Exception as e:
            raise Exception(f"[异常] 异步发送过程中发生错误，{datetime.now()}: {e} ")

async def write_single_reg(plc_client, start_add: int, val:int):
    async with plc_lock:
        response = await plc_client.write_register(address=start_add, value=val, device_id=1, no_response_expected=False)
    if response.isError():
        logger.info("写入异常")
    else:
        logger.info(f"写入成功，当前寄存器值:, {response}")        

if __name__ == "__main__":
    # 核心：启动内置 Web 容器，监听 0.0.0.0 允许局域网（手机）访问
    uvicorn.run("plc_server:app", host="0.0.0.0", port=8000, reload=True)