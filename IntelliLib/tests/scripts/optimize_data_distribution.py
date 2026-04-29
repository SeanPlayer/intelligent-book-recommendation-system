# tests/scripts/optimize_data_distribution.py
"""
数据分布优化脚本
调整数据分布，使其更符合真实场景
"""
import random
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app import create_app, db
from app.models import BorrowRecord, Rating, Book, User
from datetime import datetime, timedelta
from sqlalchemy import text

def optimize_data_distribution():
    """优化数据分布"""

    app = create_app()

    with app.app_context():
        print("🔧 开始优化数据分布...")

        # 1. 调整借阅记录状态
        print("1. 调整借阅记录状态...")

        # 获取所有借阅记录
        borrows = BorrowRecord.query.all()
        now = datetime.utcnow()

        for borrow in borrows:
            # 如果状态是borrowed但已逾期，改为overdue
            if borrow.status == 'borrowed' and borrow.due_date and borrow.due_date < now:
                # 有一定概率改为overdue（模拟部分用户逾期未还）
                if random.random() > 0.3:
                    borrow.status = 'overdue'

        db.session.commit()
        print("    借阅记录状态调整完成")

        # 2. 优化评分分布
        print("2. 优化评分分布...")

        # 确保测试用户有足够的评分
        test_users = User.query.filter(User.username.in_(['test1', 'test2'])).all()

        for user in test_users:
            # 获取用户已评分的图书
            user_ratings = Rating.query.filter_by(user_id=user.id).all()
            rated_book_ids = {r.book_id for r in user_ratings}

            # 为测试用户添加特征评分
            if user.username == 'test1':
                # test1喜欢Python和机器学习
                python_books = Book.query.filter(
                    db.or_(
                        Book.tags.like('%Python%'),
                        Book.tags.like('%机器学习%'),
                        Book.title.like('%Python%')
                    )
                ).all()

                for book in python_books[:5]:
                    if book.id not in rated_book_ids:
                        rating = Rating(
                            user_id=user.id,
                            book_id=book.id,
                            rating=random.choice([4, 5])
                        )
                        db.session.add(rating)

            elif user.username == 'test2':
                # test2喜欢Java和数据库
                java_books = Book.query.filter(
                    db.or_(
                        Book.tags.like('%Java%'),
                        Book.tags.like('%数据库%'),
                        Book.title.like('%Java%')
                    )
                ).all()

                for book in java_books[:5]:
                    if book.id not in rated_book_ids:
                        rating = Rating(
                            user_id=user.id,
                            book_id=book.id,
                            rating=random.choice([4, 5])
                        )
                        db.session.add(rating)

        # 3. 更新图书平均评分
        print("3. 更新图书统计信息...")

        books = Book.query.all()
        for book in books:
            # 更新平均评分
            book_ratings = Rating.query.filter_by(book_id=book.id).all()
            if book_ratings:
                total_rating = sum(r.rating for r in book_ratings)
                book.average_rating = round(total_rating / len(book_ratings), 1)

            # 更新借阅次数
            borrow_count = BorrowRecord.query.filter_by(book_id=book.id).count()
            book.borrow_count = borrow_count

        db.session.commit()

        # 4. 生成最终统计报告
        print("\n 数据分布优化报告：")
        print("=" * 50)

        # 用户统计
        total_users = User.query.count()
        print(f"用户总数: {total_users}")

        # 图书统计
        total_books = Book.query.count()
        active_books = Book.query.filter_by(status='active').count()
        print(f"图书总数: {total_books} (活跃: {active_books})")

        # 借阅记录统计
        borrow_stats = db.session.query(
            BorrowRecord.status,
            db.func.count(BorrowRecord.id)
        ).group_by(BorrowRecord.status).all()

        print("借阅记录状态分布:")
        for status, count in borrow_stats:
            print(f"  {status}: {count}")

        # 评分统计
        total_ratings = Rating.query.count()
        avg_rating = db.session.query(db.func.avg(Rating.rating)).scalar()
        print(f"评分总数: {total_ratings}")
        print(f"平均评分: {avg_rating:.2f}")

        # 库存检查
        bad_inventory = Book.query.filter(
            db.or_(
                Book.available_copies > Book.total_copies,
                Book.available_copies < 0
            )
        ).count()

        print(f"库存异常图书数: {bad_inventory}")

        if bad_inventory > 0:
            print("  存在库存异常，正在修复...")
            # 修复库存
            db.session.execute(text("""
                UPDATE book 
                SET available_copies = total_copies 
                WHERE available_copies > total_copies
            """))

            db.session.execute(text("""
                UPDATE book 
                SET available_copies = 0 
                WHERE available_copies < 0
            """))

            db.session.commit()
            print(" 库存已修复")

        print("=" * 50)
        print(" 数据分布优化完成！")


if __name__ == '__main__':
    optimize_data_distribution()