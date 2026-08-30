import random
import asyncio

async def gen():
    for i in range(20):
        nums=[round(random.uniform(20.0, 35.0), 1),
            round(random.uniform(4.0, 6.0), 2)     
        ]
        # print('timeout')
        await asyncio.sleep(0.2)
        print(f'i:{i}, nums: {nums}')

async def play():
    await asyncio.sleep(0.9)
    print('can we get here?')

async def test():
    task1=asyncio.create_task(gen())
    task2=asyncio.create_task(play())
    await task1
    # await task2


if __name__ == "__main__":
    asyncio.run(test())



    