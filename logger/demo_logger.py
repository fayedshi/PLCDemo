import os
import logging
from logging.handlers import RotatingFileHandler
import threading

class MyLogger:
    _instance = None
    _lock = threading.Lock()  # 确保多线程安全

    def __new__(cls, *args, **kwargs):
        """单例模式：确保整个项目只初始化一个日志实例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, log_dir="logs", log_level=logging.INFO):
        if self._initialized:
            return
        
        # 1. 创建日志存放目录
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # 2. 获取或创建名为 'project_logger' 的根日志记录器
        self.logger = logging.getLogger("project_logger")
        self.logger.setLevel(log_level)
        self.logger.propagate = False # 防止重复打印

        # 3. 定义统一的日志输出格式
        # 格式包含：时间 - 模块名 - 日志级别 - 具体信息
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 4. 配置控制台打印 (Console Handler)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # 5. 配置日志文件写入 (Rotating File Handler)
        # maxBytes=5*1024*1024 (单个文件最大 5MB), backupCount=5 (最多保留 5 个历史文件)
        log_file_path = os.path.join(log_dir, "app.log")
        file_handler = RotatingFileHandler(
            log_file_path, maxBytes=5*1024*1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        self._initialized = True

# ⚡ 直接在模块级别实例化，其他模块导入这个变量即可直接使用
logger = MyLogger().logger
