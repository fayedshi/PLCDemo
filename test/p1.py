import random
import asyncio

async def gen():
    nums=[round(random.uniform(20.0, 35.0), 1),
        round(random.uniform(4.0, 6.0), 2)     
    ]
    await asyncio.sleep(2)
    print('timeout')
    return nums


if __name__ == "__main__":
    vec=[5,6]
    vec.extend(asyncio.run(gen()))
    print(vec)
    