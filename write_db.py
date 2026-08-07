#轮询PLC并批量写表
import time
from datetime import datetime
from pymodbus.client import ModbusTcpClient
import mysql.connector

PLC_IP = "192.168.0.20"
PLC_PORT = 502

START_ADDRESS = 35
REGISTER_COUNT = 120
DEVICE_ID=1

MYSQL_CONFIG = {
    'user': 'root',
    'password': '123456',
    'host': '127.0.0.1',
    'database': 'test',
    'raise_on_warnings': True
}

def collect_and_save_to_narrow_table():
    plc_client = ModbusTcpClient(PLC_IP, port=PLC_PORT)
    if not plc_client.connect():
        print(f"[{datetime.now()}] 错误：无法连接到 PLC ({PLC_IP})")
        return
    data_buffer = []  # 内存缓冲区

    try:    
        response = plc_client.read_holding_registers(
            address=START_ADDRESS, 
            count=REGISTER_COUNT, 
            device_id=DEVICE_ID
        )
        
        if response.isError():
            print(f"警告：读取PLC 失败，跳过。错误: {response}")
            
        # 拿到该设备这组连续寄存器的原始数值列表（如）
        registers_val_list = response.registers
        
        # 【核心变化】遍历这组寄存器，把每个地址和数值拆解成独立的一行
        for index, value in enumerate(registers_val_list):
            # 实际的物理地址 = 起始地址 + 偏移索引
            register_address = START_ADDRESS + index
            
            # 打包成窄表需要的元组数据：(device_id, register_address, raw_value)
            data_buffer.append((DEVICE_ID, register_address, value))
                
    finally:
        plc_client.close()  # 确保释放 PLC 连接

    if not data_buffer:
        print("未采集到任何有效数据。")
        return

    # === 4. 批量写入 MySQL 窄表 ===
    db_conn = None
    db_cursor = None
    try:
        db_conn = mysql.connector.connect(**MYSQL_CONFIG)
        db_cursor = db_conn.cursor()
        
        # 窄表的 SQL 语句：字段与 data_buffer 中的元组严格对应
        insert_query = """
            INSERT INTO plc_register_history (device_id, register_address, raw_value) 
            VALUES (%s, %s, %s)
        """
        
        # 高效批量插入
        db_cursor.executemany(insert_query, data_buffer)
        db_conn.commit()
        
        print(f"[{datetime.now()}] 成功批量写入 {db_cursor.rowcount} 条数据到 MySQL 窄表。")
        
    except mysql.connector.Error as err:
        if db_conn:
            db_conn.rollback()
        print(f"数据库操作失败: {err}")
    finally:
        if db_cursor:
            db_cursor.close()
        if db_conn:
            db_conn.close()

# === 5. 定时服务主入口 ===
if __name__ == "__main__":
    print("物联网窄表数据采集服务已启动...")
    # while True:
    collect_and_save_to_narrow_table()
        # time.sleep(10)  # 每 10 秒执行一次全场轮询