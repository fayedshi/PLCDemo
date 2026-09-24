import random
import asyncio


async def gen():
    flag=False
    try:
        for i in range(3):
            nums=[round(random.uniform(20.0, 35.0), 1),
                round(random.uniform(4.0, 6.0), 2)     
            ]
            await asyncio.sleep(1)
            print(f'i:{i}, nums: {nums}')
        print('gen finish in normal')
        flag=True
    except asyncio.CancelledError:
        flag=False
        print('gen() cancelled')
    finally:
        return flag
    
#  0: normal finish, 1: timed out
async def check(task, duration):
    elapsed=0
    while True:
        num_int = random.randint(1, 100)
        print(f'……………………………………………………………… num in check: {num_int}')
        elapsed +=3
        if elapsed < duration:
            await asyncio.sleep(3)
        else:
            task.cancel()
            return 1
        if num_int == 34:
            task.cancel()
            return 0

async def test():
    
    task1=asyncio.create_task(gen())
    task2=asyncio.create_task(check(task1, 10))
    tasks=[]
    tasks.extend([task1,task2])
    results = await asyncio.gather(*tasks)
    print(f'results: {results}')

if __name__ == "__main__":
    asyncio.run(test())



    