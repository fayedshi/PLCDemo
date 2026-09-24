import random
import asyncio

flag=False
async def gen(flee):
    try:
        for i in range(4):
            nums=[round(random.uniform(20.0, 35.0), 1),
                round(random.uniform(4.0, 6.0), 2)     
            ]
            # print('timeout')
            await asyncio.sleep(1)
            print(f'i:{i}, nums: {nums}')
    except Exception as e:
        print('exception', e)

async def test():
    
    asyncio.create_task(gen('aa'))
    await asyncio.sleep(2)
    print('back to main')

if __name__ == "__main__":
    asyncio.run(test())



    