from pymodbus.client import AsyncModbusTcpClient
async def read_plc():
    client = AsyncModbusTcpClient('192.168.0.20', port=502)
    try:
        await client.connect()
        print("连接成功")
        # 使用 unit 替代 slave
        result = await client.read_holding_registers(address=316, count=10,device_id=1)

        if not result.isError():
            print("读取数据:", result.registers)
        else:
            print("读取失败")

        client.close()
    except Exception as e:
        print('异常',e)
    return  result.registers
    
     
