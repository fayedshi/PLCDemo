from pymodbus.client import ModbusTcpClient

from pymodbus.client import AsyncModbusTcpClient
import asyncio

lock=asyncio.Lock()
async def lauch_test():
    tasks=[]
    while True:
        tasks.append(asyncio.create_task(dosth()))
        tasks.append(asyncio.create_task(doOthers()))
        await asyncio.gather(*tasks)

async def dosth():
    
    print(f'go to do sth')

    async with lock:
        print(f'inside sth: {lock}')
        await asyncio.sleep(5)

async def doOthers():
    print(f'go to do others')

    async with lock:
        print(f'inside others: {lock}')
        await asyncio.sleep(5)        


if __name__ == "__main__":
    # print('here')
    asyncio.run(lauch_test())
    
    # res= asyncio.run(read_plc(1,1))
    # print(f'response {res}')
    # print(response)

