import random
import asyncio

async def gen():
    nums=[round(random.uniform(20.0, 35.0), 1),
        round(random.uniform(4.0, 6.0), 2)     
    ]
    await asyncio.sleep(0.2)
    print('timeout')
    return nums


if __name__ == "__main__":
   if(-4.399999999999999 > 2.1): 
       print(True)
    

