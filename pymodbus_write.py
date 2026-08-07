from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('192.168.0.20', port=502)
client.connect()

# 使用 unit 替代 slave
response = client.write_register(address=0, value=0, device_id=1, no_response_expected=False)

if  response.isError():
    print("写入异常")
else:
    print("写入成功，当前寄存器值:", response)

# 如果要同时写入多个连续的寄存器（使用 16 功能码），可以使用：
# client.write_registers(start_address, [val1, val2, val3], device_id=1)
client.close()
