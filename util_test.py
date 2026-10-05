import asyncio

from util import convert_dev_addr



    # print(f"test loadsilo: {load_silo_addrs('001')}")
async def test_run_actions():
    devices_obj={
    'windows': [1, 4], 'dampers': [2,3], 'exhaustFans': [], 'airConditioners': [], 
    'blowers': {'1': None, '2': 1, '3': None, '4': None, '5': None, '6': None, '7': 1, '8': None}
    }
    print(f"test convert_dev_addr:  {convert_dev_addr(devices_obj,'001',1)}")

  
    obj_arr=convert_dev_addr(devices_obj,'001',1)
    # for item in obj_arr:
    #     print(list(item.keys())[0])

    for index, obj in enumerate(obj_arr):
        dev_key = list(obj.keys())[0]
        print(f'index: {index}, dev_key: {dev_key}')
        act_vals = obj.get(dev_key)
        for key, move in act_vals.items():
            print(f'acting==> key {key}, move:{move}')
            # await request.app.state.write_single_reg(plc_client, int(key), move)
            # await asyncio.sleep(0.05) # 微小延时
        if dev_key =='dampers' and index==0:
            print('--------------$$$$$$$>dampers to sleep 45s')
            await asyncio.sleep(5)
    

async def test_convert_dev_addr():
    devices_obj={
    'windows': [1, 4], 'dampers': [2,3], 'exhaustFans': [], 'airConditioners': [], 
    'blowers': {'1': None, '2': 1, '3': None, '4': None, '5': None, '6': None, '7': 1, '8': None}
    }
    print(f"test convert_dev_addr:  {convert_dev_addr(devices_obj,'001',1)}")

    obj_arr = [{ "blowers": { "20": 3 } },
                { "windows": { "2": 2 } },
                { "exhaustFans": { "28": 3 } },
                { "airConditioners": {} },
                { "dampers": { "12": 2 } }]
    


if __name__ == "__main__":
   asyncio.run(test_convert_dev_addr())