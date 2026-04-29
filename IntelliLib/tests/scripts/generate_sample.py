"""
样本数据生成主脚本
生成完整的测试数据集
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app import create_app, db
from tests.test_data.user_data import UserDataGenerator
from tests.test_data.book_data import BookDataGenerator
from tests.test_data.borrow_data import BorrowDataGenerator
from tests.test_data.rating_data import RatingDataGenerator


def generate_sample_data():
    """生成完整的样本数据"""

    # 创建Flask应用上下文
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print(" 开始生成样本测试数据")
        print("=" * 60)

        # 1. 生成用户数据
        user_gen = UserDataGenerator()
        test_users = user_gen.create_test_users()  # 预定义测试用户
        random_users = user_gen.generate_random_users(25)  # 随机用户
        all_users = test_users + random_users

        print(f" 用户总数: {len(all_users)}")

        # 2. 生成图书数据
        book_gen = BookDataGenerator()
        featured_books = book_gen.create_featured_books()  # 特征图书
        random_books = book_gen.generate_random_books(40)  # 随机图书
        all_books = featured_books + random_books

        print(f" 图书总数: {len(all_books)}")

        # 3. 生成借阅记录
        borrow_gen = BorrowDataGenerator()
        borrow_gen.generate_borrow_records(all_users, all_books, 300)

        # 4. 生成评分数据
        rating_gen = RatingDataGenerator()
        rating_gen.generate_ratings(all_users, all_books, 200)

        print("=" * 60)
        print(" 样本数据生成完成！")
        print("=" * 60)

        # 显示测试账号信息
        print("\n 测试账号信息：")
        print("   普通用户: test1 / 123456 (计算机科学，高信誉分)")
        print("   普通用户: test2 / 123456 (软件工程，中等信誉分)")
        print("   管理员:   admin / admin123")

        print("\n 特征图书：")
        print("   《Python编程从入门到实践》- 测试Python相关功能")
        print("   《机器学习》- 测试AI相关功能")
        print("   《深入理解Java虚拟机》- 测试Java相关功能")


if __name__ == '__main__':
    generate_sample_data()
