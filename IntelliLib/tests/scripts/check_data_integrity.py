"""
数据完整性检查脚本
检查数据库中的数据逻辑一致性
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app import create_app, db
from app.models import Book, BorrowRecord, User, Rating


def check_data_integrity():
    """检查数据完整性"""

    app = create_app()

    with app.app_context():
        print("🔍 开始数据完整性检查...")
        print("=" * 60)

        issues = []

        # 1. 检查图书库存一致性
        print("1. 检查图书库存...")
        books = Book.query.all()
        for book in books:
            # 检查 available_copies 是否大于 total_copies
            if book.available_copies > book.total_copies:
                issues.append(
                    f"图书ID {book.id}《{book.title}》: available_copies({book.available_copies}) > total_copies({book.total_copies})")

            # 检查库存是否为负数
            if book.available_copies < 0:
                issues.append(f"图书ID {book.id}《{book.title}》: available_copies({book.available_copies}) < 0")

        print(f"   检查完成，共检查 {len(books)} 本图书")

        # 2. 检查借阅记录状态
        print("2. 检查借阅记录...")
        borrows = BorrowRecord.query.all()
        active_borrows_by_user = {}

        for borrow in borrows:
            user_id = borrow.user_id
            if borrow.status == 'borrowed':
                active_borrows_by_user[user_id] = active_borrows_by_user.get(user_id, 0) + 1

        print(f"   检查完成，共检查 {len(borrows)} 条借阅记录")

        # 3. 检查用户借阅限制
        print("3. 检查用户借阅限制...")
        users = User.query.all()
        for user in users:
            active_count = active_borrows_by_user.get(user.id, 0)
            borrow_limit = user.get_borrow_limit()

            if active_count > borrow_limit:
                issues.append(
                    f"用户ID {user.id} {user.username}: 当前借阅 {active_count} 本，超过限制 {borrow_limit} 本")

        print(f"   检查完成，共检查 {len(users)} 个用户")

        # 4. 检查评分数据
        print("4. 检查评分数据...")
        ratings = Rating.query.all()
        unique_user_book_pairs = set()
        for rating in ratings:
            pair = (rating.user_id, rating.book_id)
            if pair in unique_user_book_pairs:
                issues.append(f"重复评分: 用户ID {rating.user_id}, 图书ID {rating.book_id}")
            unique_user_book_pairs.add(pair)

        print(f"   检查完成，共检查 {len(ratings)} 条评分记录")

        # 5. 检查图书平均评分计算
        print("5. 检查图书平均评分...")
        for book in books:
            book_ratings = Rating.query.filter_by(book_id=book.id).all()
            if book_ratings:
                total_rating = sum(r.rating for r in book_ratings)
                calculated_avg = round(total_rating / len(book_ratings), 1)
                if abs(book.average_rating - calculated_avg) > 0.1:  # 允许0.1的误差
                    issues.append(
                        f"图书ID {book.id}《{book.title}》: 计算平均分 {calculated_avg} 与存储值 {book.average_rating} 不一致")

        print("=" * 60)

        # 输出检查结果
        if issues:
            print("❌ 发现以下问题：")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
            print(f"\n共发现 {len(issues)} 个问题")
        else:
            print("✅ 数据完整性检查通过，未发现问题")

        return len(issues) == 0


if __name__ == '__main__':
    success = check_data_integrity()
    sys.exit(0 if success else 1)
    
    