# tests/test_data/borrow_data.py
import random
from datetime import datetime, timedelta
from faker import Faker
from app import db
from app.models import BorrowRecord

class BorrowDataGenerator:
    def __init__(self):
        self.fake = Faker('zh_CN')

    def _get_user_interest_set(self, user):
        """获取用户兴趣标签集合"""
        tags = set()
        if user.interest_tags:
            tags.update([t.strip() for t in user.interest_tags.split(',') if t.strip()])
        return tags

    def _get_book_tag_set(self, book):
        """获取图书标签集合"""
        if not book.tags:
            return set()
        return set([t.strip() for t in book.tags.split(',') if t.strip()])

    def generate_borrow_records(self, users, books, count=2000):
        print(f"📖 生成 {count} 条借阅记录（含探索机制）...")
        borrow_records = []
        attempts = 0
        max_attempts = count * 3
        now = datetime.utcnow()

        # 为每个用户生成探索率（0~0.3）
        user_explore_rate = {u.id: random.uniform(0, 0.3) for u in users}

        # 预计算兴趣集和标签集
        user_interest = {u.id: self._get_user_interest_set(u) for u in users}
        book_tags = {b.id: self._get_book_tag_set(b) for b in books}

        while len(borrow_records) < count and attempts < max_attempts:
            attempts += 1
            user = random.choice(users)
            explore_rate = user_explore_rate[user.id]
            interest_set = user_interest[user.id]

            # 决定是否探索
            if interest_set and random.random() > explore_rate:
                # 兴趣驱动：选择与兴趣有交集的图书
                candidates = [b for b in books if book_tags[b.id] & interest_set]
                if not candidates:
                    candidates = books
                book = random.choice(candidates)
            else:
                # 随机探索
                book = random.choice(books)

            if book.available_copies <= 0:
                continue

            # 借阅时间分布（使数据有近期趋势）
            time_category = random.choices(
                ['recent', 'medium', 'old'],
                weights=[0.4, 0.4, 0.2]  # 近期更多
            )[0]
            if time_category == 'recent':
                borrow_date = self.fake.date_time_between(
                    start_date=now - timedelta(days=30),
                    end_date=now
                )
            elif time_category == 'medium':
                borrow_date = self.fake.date_time_between(
                    start_date=now - timedelta(days=180),
                    end_date=now - timedelta(days=30)
                )
            else:
                borrow_date = self.fake.date_time_between(
                    start_date=now - timedelta(days=365),
                    end_date=now - timedelta(days=180)
                )

            # 决定是否归还（归还概率随借阅时间增长而增加）
            if (now - borrow_date).days > 30:
                return_prob = 0.9  # 很久以前借的，大概率已还
            elif (now - borrow_date).days > 7:
                return_prob = 0.7
            else:
                return_prob = 0.3

            if random.random() < return_prob:
                # 归还，归还日期在借阅后几天到几个月之间
                return_days = random.randint(5, 90)
                return_date = borrow_date + timedelta(days=return_days)
                # 确保归还日期不晚于当前时间
                if return_date > now:
                    return_date = now
                status = 'returned'
                book.available_copies += 1
            else:
                return_date = None
                status = 'borrowed'
                book.available_copies -= 1

            due_date = borrow_date + timedelta(days=30)  # 默认30天借期
            # 如果逾期未还且当前未还，标记为 overdue
            if status == 'borrowed' and due_date < now:
                if random.random() > 0.3:
                    status = 'overdue'

            renew_count = 0
            if status in ['borrowed', 'overdue'] and random.random() > 0.8:
                renew_count = random.randint(1, 2)
                due_date += timedelta(days=renew_count * 15)

            record = BorrowRecord(
                user_id=user.id,
                book_id=book.id,
                borrow_date=borrow_date,
                due_date=due_date,
                return_date=return_date,
                status=status,
                renew_count=renew_count,
                rating=None
            )
            db.session.add(record)
            borrow_records.append(record)

            if len(borrow_records) % 200 == 0:
                db.session.commit()

        db.session.commit()
        print(f"✅ 成功创建 {len(borrow_records)} 条借阅记录")
        return borrow_records