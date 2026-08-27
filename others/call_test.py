from pymodbus_read import read_plc
# from async_pymodbus_read import read_plc
import asyncio

response=read_plc()
print(response)