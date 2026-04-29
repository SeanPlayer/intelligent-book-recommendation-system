
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, Book, Wishlist, BorrowRecord, Rating, CreditConfig, Notification, Exposure, UserAction, DEFAULT_CREDIT_CONFIGS

app = create_app()

with app.app_context():
    print(" 开始重置数据库...")

    # 删除所有表
    db.drop_all()
    print(" 已删除所有表")

    # 重新创建表（使用新的模型结构）
    db.create_all()
    print(" 已重新创建所有表")

    # 显示创建的表
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f" 当前数据库中的表: {tables}")

    print(" 数据库重置完成！")







