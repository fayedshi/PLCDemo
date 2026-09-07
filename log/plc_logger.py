import logging

def get_logger():
    # 1. 创建全局日志记录器 (Logger)
    logger = logging.getLogger("my_project_logger")
    logger.setLevel(logging.DEBUG)  # 允许捕获最低 DEBUG 级别的日志

    # 2. 创建一个输出到控制台的处理器 (Handler)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # 控制台只看 INFO 及以上

    # 3. 创建一个输出到文件的处理器 (Handler)
    file_handler = logging.FileHandler("app.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)  # 文件中记录最详尽的 DEBUG 级日志

    # 4. 定义日志的排版格式 (Formatter)
    console_format = logging.Formatter('%(levelname)s: %(message)s')
    file_format = logging.Formatter('%(asctime)s - %(name)s - [%(filename)s:%(lineno)d] - %(levelname)s - %(message)s')

    # 5. 绑定格式到处理器，再将处理器绑定到记录器
    console_handler.setFormatter(console_format)
    file_handler.setFormatter(file_format)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # 6. 在代码中使用 logger 打印日志
    logger.info("系统初始化开始...")
    logger.debug("隐蔽的调试变量: x = 42")
    return logger
