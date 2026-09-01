
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings
import argparse


# 1. 解析参数并加载环境（必须在最外层）
parser = argparse.ArgumentParser()
parser.add_argument('--env', choices=['dev', 'test'], default='dev')
args, _ = parser.parse_known_args()
# load_dotenv(dotenv_path=f".env.{args.env}")

env_filename=f".env.{args.env}"
print(f"env_filename: {env_filename}")
class Settings(BaseSettings):
    # Pydantic 会自动读取名为 DATABASE_URL 的环境变量
    # 默认值是一个本地的 MySQL 数据库地址
    DATABASE_URL: str = "mysql+aiomysql://root:123456@localhost:3306/test"
    DB_HOST: str
    DB_PORT: str
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    model_config={
        "env_file": env_filename, # 支持从项目根目录的 .env 文件加载
        "extra": 'ignore'
    }
# 实例化配置对象
settings = Settings()
