from pymodbus import ModbusException
from pymodbus.client import AsyncModbusTcpClient
import asyncio
from datetime import datetime

def my_internal_reconnect_print():
    print("【Modbus通知】pymodbus 底层刚刚默默发起了一次新的 TCP 自动重连动作！")


async def read_plc(start_address:int, len:int):
    client = AsyncModbusTcpClient('10.0.0.7', port=502,
        reconnect_delay=2.0,      # 第一次断线，等 1 秒就去连)
        reconnect_delay_max=120.0,
        timeout=3.0,
        trace_connect = my_internal_reconnect_print 
    )
    await client.connect()
    while True:
        try:
            
            if not client.connected:
                print("⏳ 链路当前未连通，等待 pymodbus 后台自动握手重连...")
                await asyncio.sleep(3)
                continue
            # 使用 unit 替代 slave
            result = await client.read_holding_registers(address=start_address,count=len, device_id=1)

            if not result.isError():
                print("读取数据:", result.registers)
            else:
                print("读取失败")
            # client.close()
            return  result.registers
        except Exception as e:
            print('连接断开，准备自动重连',e,datetime.now())
    
    
if __name__ == "__main__":
    response=asyncio.run(read_plc(316,10))
    print(response)