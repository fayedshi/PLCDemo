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

    js_obj= {6:'apple',8:'doe'}
    
    print(list(js_obj.values()))

    key_list=  [_key for _key in js_obj.keys()]

    print(key_list)

    for dev_index,val in enumerate(key_list):
        print(f'index: {dev_index} val: {val}')
 
    val=0
    try:
        val= key_list[2]
        
    except Exception as  e:
        val=None 
    
    print(f'val {val}')
    for key in js_obj.keys():
        print(f'my key: {key}')

    js={}
    if not js:
        print('test ok')

    str_t=''
    if not str_t:
        print('empty string')


