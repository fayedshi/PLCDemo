import random
import asyncio

async def gen():
    for i in range(3):
        nums=[round(random.uniform(20.0, 35.0), 1),
            round(random.uniform(4.0, 6.0), 2)     
        ]
        # print('timeout')
        await asyncio.sleep(1)
        print(f'i:{i}, nums: {nums}')
    return True
async def play():
    # await asyncio.sleep(0.9)
    print('can we get here?')

async def test():
    task1= asyncio.create_task(gen())
    print('created task1')
    # task2=asyncio.create_task(play())
    
    # await asyncio.sleep(6)
    # yield
    
    try:
        result = await asyncio.wait_for(task1, timeout=5.0)
        print(' done within time limi',result)
    except asyncio.TimeoutError:
        print("【超时错误】: 任务执行超过了设定的 2 秒限制，已被强制终止！")
        print(f"任务是否被取消: {task1.cancelled()}") 
    print('back to main')

if __name__ == "__main__":
    asyncio.run(test())



    