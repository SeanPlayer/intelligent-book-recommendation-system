import sys
import os
import random
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from app import create_app, db
from app.models import BorrowRecord, Rating

def generate_ratings_from_borrows():
    app = create_app()
    with app.app_context():
        print("开始生成评分...")
        # 获取所有已归还且有持有时长的借阅记录（山东农大数据集有 HOLDTIME 字段，我们导入时可能未存）
        # 注意：我们的 BorrowRecord 表中没有 holdtime 字段，需要从源数据补充？或者直接用 borrow_date 和 return_date 计算
        records = BorrowRecord.query.filter(BorrowRecord.return_date.isnot(None)).all()
        count = 0
        for br in records:
            # 计算持有时长（小时）
            if br.return_date and br.borrow_date:
                delta = br.return_date - br.borrow_date
                hours = delta.total_seconds() / 3600
                # 映射评分
                if hours < 24:
                    rating = random.choice([1,2])
                elif hours < 7*24:
                    rating = random.choice([2,3])
                elif hours < 14*24:
                    rating = random.choice([3,4])
                else:
                    rating = random.choice([4,5])
            else:
                # 没有归还日期的（理论上不应存在），跳过
                continue

            # 检查是否已存在评分
            existing = Rating.query.filter_by(user_id=br.user_id, book_id=br.book_id).first()
            if existing:
                # 可以更新，但保持一致性（可选）
                existing.rating = rating
                existing.created_at = br.return_date or datetime.utcnow()
            else:
                rating_obj = Rating(
                    user_id=br.user_id,
                    book_id=br.book_id,
                    rating=rating,
                    created_at=br.return_date or datetime.utcnow()
                )
                db.session.add(rating_obj)
            count += 1
            if count % 500 == 0:
                db.session.commit()
                print(f"已处理 {count} 条")
        db.session.commit()
        print(f"评分生成完成，共处理 {count} 条借阅记录。")

        # 更新图书平均评分
        from app.models import Book
        books = Book.query.all()
        for book in books:
            ratings = Rating.query.filter_by(book_id=book.id).all()
            if ratings:
                book.average_rating = round(sum(r.rating for r in ratings) / len(ratings), 1)
        db.session.commit()
        print("图书平均评分已更新。")

if __name__ == '__main__':
    generate_ratings_from_borrows()