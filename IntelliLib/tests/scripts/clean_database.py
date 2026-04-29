# tests/scripts/clean_database.py
"""
清理数据库数据脚本 - 慎用！
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app import create_app, db
from app.models import User, Book, BorrowRecord, Rating


def clean_database(keep_admin=True):
    """清理数据库，保留管理员账号"""
    app = create_app()

    with app.app_context():
        print("⚠️  警告：即将清理数据库！")
        confirm = input("请输入 'YES' 确认清理：")

        if confirm != 'YES':
            print("取消清理操作")
            return

        print("开始清理数据库...")

        # 删除借阅记录
        BorrowRecord.query.delete()
        print("✅ 清理借阅记录")

        # 删除评分记录
        Rating.query.delete()
        print("✅ 清理评分记录")

        # 删除图书
        Book.query.delete()
        print("✅ 清理图书数据")

        # 删除用户（可选保留管理员）
        if keep_admin:
            User.query.filter(User.role != 'admin').delete()
            print("✅ 清理普通用户数据（保留管理员）")
        else:
            User.query.delete()
            print("✅ 清理所有用户数据")

        db.session.commit()
        print("🎉 数据库清理完成！")


if __name__ == '__main__':
    clean_database(keep_admin=True)
