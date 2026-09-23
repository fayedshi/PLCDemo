
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings
import argparse
import os
import yaml


def load_config():
    args = read_args()
    with open(f'{args.env}.yaml', 'r', encoding='utf-8') as file:
        # 2. 使用 yaml.safe_load 读取文件内容
        config_data = yaml.safe_load(file)
        return config_data

def read_args():
# 1. 解析参数并加载环境（必须在最外层）
    parser = argparse.ArgumentParser()
    parser.add_argument('--env', choices=['dev', 'test'], default='dev')
    args, _ = parser.parse_known_args()
    return args

_raw_config = load_config()

class Settings(BaseSettings):
    # def __init__(self):
        
    #     self._config= load_config()

    @property
    def raw_config(self) -> object:
        return _raw_config

    @property
    def granaries(self) -> list:
        return _raw_config.get("granaries", [])

    @property
    def sched_max_wait(self) -> int:
            return _raw_config.get("SCHED_MAX_WAIT", 300)
    # @property
    # def debug(self) -> bool:
    #     return self._config.get("app", {}).get("debug", False)

    # @property
    # def enable_auth(self) -> bool:
    #     return self._config.get("api", {}).get("enable_auth", False)
   
# 实例化配置对象

settings = Settings()
