# for i in range(140):
#     print(f'temp{i},')

from log.plc_logger import get_logger

temp_cols = [f"temp{i}" for i in range(120,140)]
temp_all_cols = ", ".join(temp_cols)    

logger=get_logger();

logger.info(temp_all_cols)