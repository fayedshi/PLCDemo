# from pymodbus_read import read_plc
from async_pymodbus_read import read_plc, registers_to_val
import asyncio
# from util import   registers_to_val



raw_regs=asyncio.run(read_plc(405,10))


data = []
        # 每次跳 2 步
for i in range(0, len(raw_regs), 2):
    # pair = data[i:i+2]
    
    if i==len(raw_regs)-2:
        print(f'power data regs: {raw_regs[i]},{raw_regs[i+1]}')
        consumEnerg=round(registers_to_val(raw_regs[i],raw_regs[i+1],'I')/1000,2)
        data.append(consumEnerg)
    else:
        data.append(registers_to_val(raw_regs[i],raw_regs[1+1],'f'))

print(data)
# result=registers_to_val(reg_data[0],reg_data[1])

# print(f'val,{round(result/1000,2)}')