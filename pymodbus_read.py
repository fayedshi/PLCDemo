from pymodbus.client import ModbusTcpClient

def read_plc():

    client = ModbusTcpClient('192.168.0.20', port=502)
    client.connect()

    # 使用 unit 替代 slave
    result = client.read_holding_registers(address=316, count=10,device_id=1)

    if not result.isError():
        print("读取数据:", result.registers)
    else:
        print("读取失败")

    client.close()
    return  result.registers
    

# print(read_plc())          
