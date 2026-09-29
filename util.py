import time
import asyncio
import struct
from config import settings

async def build_influx_line_protocol(measurement, tags, fields, timestamp_ns=None):
    """
    动态将字典转换为 InfluxDB 3 标准行协议格式
    :param measurement: 表名 (str)
    :param tags: 标签字典 (dict)
    :param fields: 400个字段数据的字典 (dict)
    :param timestamp_ns: 纳秒时间戳，如果不传则使用当前时间
    """

    try:
        # print('within build_influx_line_protocol')
        # 1. 动态拼接 Tags (例如: device_id=plc_01,area=workshop_A)
        tag_str = ",".join([f"{k}={v}" for k, v in tags.items()])
        measurement_and_tags = f"{measurement},{tag_str}" if tag_str else measurement
        
        # 2. 动态拼接 400 个 Fields (例如: temp1=23.5,press2=101.3...)
        field_list = []
        for k, v in fields.items():
            # if v==63036:# innormal figure to skip
            #     print(f"****************************Invalid value found: {v}")
            #     print('PLC内部异常，等待2分钟...')
            #     await asyncio.sleep(120)
            #     raise Exception('【错误：】PLC读到异常数据')
            if isinstance(v, float):
                field_list.append(f"{k}={v}")  # 浮点数直接拼接
            elif isinstance(v, int):
                field_list.append(f"{k}={v}i") # 整数需要加 i 后缀
            elif isinstance(v, str):
                field_list.append(f'{k}="{v}"') # 字符串需要加双引号
                
        field_str = ",".join(field_list)
        
        # 3. 处理时间戳 (默认为当前纳秒时间戳)
        if timestamp_ns is None:
            timestamp_ns = time.time_ns()

        # timestamp_ns=1787304318447622000
        # 4. 组合成行协议：西门子数据_表名,标签 字段1=值1,字段2=值2 时间戳
        line = f"{measurement_and_tags} {field_str} {timestamp_ns}"
        # print(line)
        return line
    except Exception as e:
        raise Exception(f'build_influx_line_protocol 发生异常, {e}')


    
def registers_to_val(reg_high, reg_low, flag):
    """
    将西门子 PLC 的两个 16 位寄存器转换为 32 位浮点数
    :param reg_high: 第一个寄存器（地址较小的，高 16 位）
    :param reg_low: 第二个寄存器（地址较大的，低 16 位）
    """
    # 按照大端序格式将两个 16 位无符号整数(H)打包成 4 字节二进制数据
    raw_bytes = struct.pack(">HH", reg_high, reg_low)
    
    # 将这 4 字节数据按照大端序解包为 32 双整形(f)
    dint_val = struct.unpack(f">{flag}", raw_bytes)[0]
    return dint_val


def get_reg_start_addr(silo, dev_name):
    # ext_temp_addr =granaries[index]['devices_addr']['ext-temp'][0]
    return silo['devices_addr'][dev_name][0]

# return devices_addr json object
def load_silo_addrs(house_code) -> object:
    granaries=settings.granaries
    house_index = int(house_code) -1
    return granaries[house_index]['devices_addr']

def convert_dev_addr(devices, house_code, flag):
    # {
    # 'windows': [1, 4], 'dampers': [], 'exhaustFans': [], 'airConditioners': [], 
    # 'blowers': {'1': None, '2': 1, '3': None, '4': None, '5': None, '6': None, '7': 1, '8': None}
    # }
    silo_addrs= load_silo_addrs(house_code)
    # print('devices: ',devices)
    # print('silo in convert_dev_addr:', silo_addrs)
    blowers = devices['blowers']
    blower_offset= silo_addrs['blowers'][0]
    action_val=1
    if not flag:
        action_val=3
    filtered_blowers =  {'blowers': {int(key) + blower_offset - 1: action_val for key, value in blowers.items() if value is not None}}
    # print(f'filtered_blowers {filtered_blowers}')
    filtered_dict={}
    # devices.pop("blowers", None) 
    # print(f'left devices {devices}')

    for key, value in devices.items():
        # print(f"键: {key} -> 值: {value}")
        if key=='blowers':
            continue
        addrs=devices[key]
        offset=silo_addrs[key][0]
        if flag:
            action_val=1
        elif key=='exhaustFans':
            action_val=3
        else:
            action_val=2
        filtered_dict =filtered_dict| {key: {num + offset - 1: action_val for num in addrs}}
    merged_dict = filtered_blowers | filtered_dict
    return merged_dict

async def execute_commands(request, action_obj,):
    target_keys = ['blowers', 'exhaustFans']
    #先开风门
    if any(key in action_obj for key in target_keys) and 'dampers' in action_obj:
        # oper dampers first
        damper_keys=[]
        for key,val in action_obj['dampers'].items():
            print(f'writing to dampers at {key}')
            # await write_single_step(plc_client, key,val)
        
        asyncio.sleep(45)
            # damper_keys.push(key)
        # wait til dampers opened/closed fully, or wait for 45 ses arbitraly

        # damper_regs=await partial_read(plc_client, key,1)


    # plc_client = request.app.state.plc_conns[house_index]
    for key, value in action_obj.items():
        await request.app.state.write_single_reg(plc_client, int(key), value)
        await asyncio.sleep(0.05) # 微小延时

if __name__ == "__main__":
    # print(f"test loadsilo: {load_silo_addrs('001')}")

    devices_obj={
    'windows': [1, 4], 'dampers': [2], 'exhaustFans': [], 'airConditioners': [], 
    'blowers': {'1': None, '2': 1, '3': None, '4': None, '5': None, '6': None, '7': 1, '8': None}
    }
    print(f"test convert_dev_addr:  {convert_dev_addr(devices_obj,'001',1)}")

