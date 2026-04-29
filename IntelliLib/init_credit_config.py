import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import CreditConfig, DEFAULT_CREDIT_CONFIGS

app = create_app()


def init_credit_config():
    with app.app_context():
        print(" 初始化信誉分配置...")

        for key, value in DEFAULT_CREDIT_CONFIGS.items():
            CreditConfig.set_config(key, value)
            print(f" 已设置: {key} = {value}")

        print(" 信誉分配置初始化完成！")


if __name__ == '__main__':
    init_credit_config()
