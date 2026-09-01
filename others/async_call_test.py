# from pymodbus_read import read_plc
from async_pymodbus_read import read_plc, registers_to_float
import asyncio

reg_data=asyncio.run(read_plc(413,2))


result=registers_to_float(reg_data[0],reg_data[1])

print(result)