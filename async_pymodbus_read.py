from pymodbus.client import AsyncModbusTcpClient
import asyncio
async def read_plc(start_address:int, len:int):
    client = AsyncModbusTcpClient('192.168.0.20', port=502)
    try:
        await client.connect()
        print("连接成功")
        # 使用 unit 替代 slave
        result = await client.read_holding_registers(address=start_address,count=len, device_id=1)

        if not result.isError():
            print("读取数据:", result.registers)
        else:
            print("读取失败")
        client.close()
        return  result.registers
    except Exception as e:
        print('异常',e)
    
    

if __name__ == "__main__":
    response=asyncio.run(read_plc(316,10))
    print(response)