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

    await write_single_step(21,3)
    print('ready to read again')
    # await read_single_step(363,1)


if __name__ == "__main__":
    print('here')
    asyncio.run(write_plc())
    
    # res= asyncio.run(read_plc(1,1))
    # print(f'response {res}')
    # print(response)