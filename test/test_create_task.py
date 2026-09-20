import random
import asyncio

flag=False
async def gen():
    global flag
    try:
        for i in range(4):
            nums=[round(random.uniform(20.0, 35.0), 1),
                round(random.uniform(4.0, 6.0), 2)     
            ]
            # print('timeout')
            await asyncio.sleep(1)
            print(f'i:, nums: {nums}')
        flag=True
    finally:
        # flag=True
        return flag
    
async def play():
    # await asyncio.sleep(0.9)
    print('can we get here?')

async def test():
    task1= asyncio.create_task(gen())
    # task2=asyncio.create_task(play())
    
    await asyncio.sleep(5)
    print(f'flag: {flag}')
    # yield
    print('back to main')

if __name__ == "__main__":
    asyncio.run(test())



    