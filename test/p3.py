import random
import asyncio

async def gen():
    try:
        for i in range(10):
            nums=[round(random.uniform(20.0, 35.0), 1),
                round(random.uniform(4.0, 6.0), 2)     
            ]
            # print('timeout')
            await asyncio.sleep(3)
            print(f'i:{i}, nums: {nums}')
    except TimeoutError as e:
        print(e)

async def play():
    # await asyncio.sleep(0.9)
    print('can we get here?')

async def test():
    # await task1
    # tasks=[]
    # tasks.append(task1)
    # tasks.append(task2)

    # await asyncio.gather(*tasks)

    while True:
        task1=asyncio.create_task(gen())
        task2=asyncio.create_task(play())
        tasks=[]
        tasks.append(task1)
        tasks.append(task2)
        await asyncio.gather(*tasks)
        print('#############in test')

        await asyncio.sleep(3)
        print('back to main')


if __name__ == "__main__":
    asyncio.run(test())



    