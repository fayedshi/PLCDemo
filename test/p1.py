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
    vec=[5,6]
    vec.extend(asyncio.run(gen()))
    print(vec)
    plc_channels = {}
    for i in range(1, 10):
        plc_channels[f"sensor_ch{i}"] = 23.45 + (i * 0.1)  # 模拟数据如: 23.55, 23.65...

    print(plc_channels)


    