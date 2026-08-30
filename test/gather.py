import asyncio

async def task_a():
    while True:
        print('runing task a')
        # 🌟 关键：主动交出控制权，哪怕只睡 0 秒，也能让 task_b 跑起来
        await asyncio.sleep(1)  # 建议稍微睡一下，否则打印太快会卡死终端

async def task_b():
    while True:
        print('runing task b')
        # 🌟 关键：同理，干完一轮活，让出控制权
        await asyncio.sleep(1)

async def main_task():
    # 这样它们就能真正齐头并进、交替在后台运行了
    await asyncio.gather(task_a(), task_b())

if __name__ == "__main__":
    # 对应你伪代码里的 main: asyncio.run(main_task())
    asyncio.run(main_task())
