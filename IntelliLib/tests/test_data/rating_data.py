# tests/test_data/rating_data.py
import random
import numpy as np
from datetime import datetime
from app import db
from app.models import Rating, BorrowRecord, Book

class RatingDataGenerator:
    def _get_user_interest_set(self, user):
        tags = set()
        if user.interest_tags:
            tags.update([t.strip() for t in user.interest_tags.split(',') if t.strip()])
        return tags

    def _get_book_tag_set(self, book):
        if not book.tags:
            return set()
        return set([t.strip() for t in book.tags.split(',') if t.strip()])

    def generate_ratings(self, users, books, count=1000):
        print(f"⭐ 生成 {count} 条评分数据（基于兴趣匹配+噪声）...")
        ratings_created = 0

        # 预计算兴趣集和标签集
        user_interest = {u.id: self._get_user_interest_set(u) for u in users}
        book_tags = {b.id: self._get_book_tag_set(b) for b in books}

        # 只对已归还的借阅记录生成评分
        returned_borrows = BorrowRecord.query.filter_by(status='returned').all()
        random.shuffle(returned_borrows)

        for borrow in returned_borrows:
            if ratings_created >= count:
                break

            # 检查是否已有评分
            existing = Rating.query.filter_by(
                user_id=borrow.user_id, book_id=borrow.book_id
            ).first()
            if existing:
                continue

            u_interest = user_interest.get(borrow.user_id, set())
            b_tags = book_tags.get(borrow.book_id, set())

            # 计算兴趣匹配度（Jaccard）
            if u_interest and b_tags:
                match = len(u_interest & b_tags) / len(u_interest)
            else:
                match = random.uniform(0, 0.3)  # 没有标签则随机低匹配

            # 基础评分：匹配度映射到1~5
            base_rating = 1 + match * 4  # 1~5线性

            # 加入高斯噪声（标准差0.5），并截断到1~5
            noise = np.random.normal(0, 0.5)
            rating_value = base_rating + noise
            rating_value = max(1, min(5, rating_value))

            # 意外惊喜：5%的概率给高分（即使匹配度低）
            if random.random() < 0.05:
                rating_value = random.uniform(4, 5)

            rating_value = round(rating_value)

            # 确保评分在1~5之间
            rating_value = max(1, min(5, rating_value))

            rating = Rating(
                user_id=borrow.user_id,
                book_id=borrow.book_id,
                rating=rating_value,
                created_at=borrow.return_date or datetime.utcnow()
            )
            db.session.add(rating)
            ratings_created += 1

            if ratings_created % 200 == 0:
                db.session.commit()

        db.session.commit()
        # 更新图书平均评分
        all_books = Book.query.all()
        for book in all_books:
            book_ratings = Rating.query.filter_by(book_id=book.id).all()
            if book_ratings:
                total = sum(r.rating for r in book_ratings)
                book.average_rating = round(total / len(book_ratings), 1)
        db.session.commit()

        print(f"✅ 成功创建 {ratings_created} 条评分数据")
        return ratings_created