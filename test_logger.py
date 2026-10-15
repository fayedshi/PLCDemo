# for i in range(140):
#     print(f'temp{i},')

from logger.demo_logger import logger

# temp_cols = [f"temp{i}" for i in range(120,140)]
# temp_all_cols = ", ".join(temp_cols)    

# logger=get_logger();

temp_cols = [f"temp{i}" for i in range(0,140,4)  if i> 30]
temp_all_cols = ", ".join(temp_cols)    
logger.info(temp_all_cols)
test_str=''
for i in range(1,4):
    test_str= f'{test_str},{i}'
print(test_str)
