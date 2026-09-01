from pymodbus.client import AsyncModbusTcpClient
import asyncio
import struct

async def read_plc(start_address:int, len:int):
    client = AsyncModbusTcpClient('192.168.0.20', port=503)
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
    

def registers_to_int(reg_high, reg_low):
    """
    将西门子 PLC 的两个 16 位寄存器转换为 32 位浮点数
    :param reg_high: 第一个寄存器（地址较小的，高 16 位）
    :param reg_low: 第二个寄存器（地址较大的，低 16 位）
    """
    # 按照大端序格式将两个 16 位无符号整数(H)打包成 4 字节二进制数据
    raw_bytes = struct.pack(">HH", reg_high, reg_low)
    
    # 将这 4 字节数据按照大端序解包为 32 位浮点数(f)
    dint_value = struct.unpack(">I", raw_bytes)[0]
    
    return dint_value

    
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

if __name__ == "__main__":
    response=asyncio.run(read_plc(316,10))
    print(response)