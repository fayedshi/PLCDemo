import yaml
import argparse


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