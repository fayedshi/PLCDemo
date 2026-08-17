from pymodbus.client import ModbusTcpClient
from async_pymodbus_read import read_plc
from pymodbus.client import AsyncModbusTcpClient
import asyncio

client=None


async def write_single_step(start_add: int, val:int):
    response = await client.write_register(address=start_add, value=val, device_id=1, no_response_expected=False)
    if response.isError():
        print("写入异常")
    else:
        print("写入成功，当前寄存器值:", response)       

         
async def write_multi_regs(start_add: int, vals:list[int]):
    response = await client.write_registers(address=start_add, values=vals, device_id=1, no_response_expected=False)
    if response.isError():
        print("写入异常")
    else:
        print("写入成功，当前寄存器值:", response)        


async def read_single_step(start_add: int, len: int):
    result = await client.read_holding_registers(address=start_add,count=len, device_id=1)
    if not result.isError():
        print("读取数据:", result.registers)
    else:
        print("读取失败")    

async def write_plc():
    global client
    client=AsyncModbusTcpClient('192.168.0.20', port=502) 
    await client.connect()
    print('connected to PLC')
    # 使用 unit 替代 slave
    # 本地远程切换，
    await write_single_step(0,2)
    # 手动自动切换
    await write_single_step(399,2)

    # 写入1号窗控，开窗
    # await write_single_step(1,2)
    await write_multi_regs(3,[2])
    # response = await client.write_register(address=1, value=1, device_id=1, no_response_expected=False)
   
    print('ready to read again')
    # 读取一号窗状态
    # result = await client.read_holding_registers(address=365,count=1, device_id=1)
    # if not result.isError():
    #     print("读取数据:", result.registers)
    # else:
    #     print("读取失败")
    await read_single_step(365,3)

    client.close()
    print('disconnected')
    # 如果要同时写入多个连续的寄存器（使用 16 功能码），可以使用：
    # client.write_registers(start_address, [val1, val2, val3], device_id=1)
    
if __name__ == "__main__":
    print('here')
    asyncio.run(write_plc())
    
    # res= asyncio.run(read_plc(1,1))
    # print(f'response {res}')
    # print(response)