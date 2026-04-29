# tests/scripts/generate_smart.py
"""
智能数据生成脚本 - 根据现有数据状态生成测试数据
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app import create_app, db
from tests.test_data.user_data import UserDataGenerator
from tests.test_data.book_data import BookDataGenerator
from tests.test_data.borrow_data import BorrowDataGenerator
from tests.test_data.rating_data import RatingDataGenerator
from app.models import User, Book, BorrowRecord, Rating


def analyze_database():
    """分析数据库当前状态"""
    app = create_app()

    with app.app_context():
        stats = {
            'user_count': db.session.query(db.func.count(User.id)).scalar(),
            'book_count': db.session.query(db.func.count(Book.id)).scalar(),
            'borrow_count': db.session.query(db.func.count(BorrowRecord.id)).scalar(),
            'rating_count': db.session.query(db.func.count(Rating.id)).scalar()
        }
        return stats


def generate_smart_data():
    """智能生成测试数据"""

    app = create_app()

    with app.app_context():
        print(" 分析数据库当前状态...")
        stats = analyze_database()

        print(f"   用户数量: {stats['user_count']}")
        print(f"   图书数量: {stats['book_count']}")
        print(f"   借阅记录: {stats['borrow_count']}")
        print(f"   评分记录: {stats['rating_count']}")

        print("=" * 60)
        print(" 智能生成测试数据")
        print("=" * 60)

        # 1. 用户数据生成
        user_gen = UserDataGenerator()
        if stats['user_count'] < 300:  # 如果没有足够的测试用户
            print(" 生成测试用户...")
            test_users = user_gen.create_test_users()
            if test_users is None:
                test_users = []
            random_user_count = min(300, 100 - stats['user_count'])
            random_users = user_gen.generate_random_users(random_user_count)
            if random_users is None:
                random_users = []
            all_users = test_users + random_users
        else:
            print(" 已有足够用户，跳过用户生成")
            all_users = User.query.all()


        # 2. 图书数据生成
        book_gen = BookDataGenerator()
        if stats['book_count'] < 500:
            print(" 生成测试图书...")
            featured_books = book_gen.create_featured_books()
            if featured_books is None:
                featured_books = []
            random_books = book_gen.generate_random_books(500)
            if random_books is None:
                random_books = []
            all_books = featured_books + random_books
        else:
            print(" 已有足够图书，跳过图书生成")
            all_books = Book.query.all()


        # 3. 借阅记录生成
        if stats['borrow_count'] < 1000:  # 如果借阅记录不足
            print(" 生成借阅记录...")
            borrow_gen = BorrowDataGenerator()
            borrow_gen.generate_borrow_records(all_users, all_books, 1500)
        else:
            print(" 已有足够借阅记录，跳过生成")

        # 4. 评分数据生成
        if stats['rating_count'] < 300:  # 如果评分记录不足
            print(" 生成评分数据...")
            rating_gen = RatingDataGenerator()
            rating_gen.generate_ratings(all_users, all_books, 1000)
        else:
            print(" 已有足够评分记录，跳过生成")

        # 生成最终统计数据
        final_stats = analyze_database()

        print("=" * 60)
        print(" 智能数据生成完成！")
        print("=" * 60)

        print("\n 最终数据统计：")
        print(f"   用户总数: {final_stats['user_count']} 人")
        print(f"   图书总数: {final_stats['book_count']} 本")
        print(f"   借阅记录: {final_stats['borrow_count']} 条")
        print(f"   评分记录: {final_stats['rating_count']} 条")

        # 显示测试账号信息
        test1 = User.query.filter_by(username='test1').first()
        test2 = User.query.filter_by(username='test2').first()
        admin = User.query.filter_by(username='admin').first()

        print("\n 测试账号信息：")
        if test1:
            print(f"   普通用户: {test1.username} / 123456")
        if test2:
            print(f"   普通用户: {test2.username} / 123456")
        if admin:
            print(f"   管理员:   {admin.username} / admin123")


if __name__ == '__main__':
    generate_smart_data()

