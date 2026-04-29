
import numpy as np
from collections import defaultdict
from app.models import User, Book, Rating, BorrowRecord
import random

class FMRecommender:
    def __init__(self, n_factors=20, learning_rate=0.01, reg=0.02, n_epochs=50):
        self.n_factors = n_factors
        self.lr = learning_rate
        self.reg = reg
        self.n_epochs = n_epochs
        self.user_factors = None
        self.item_factors = None
        self.user_map = {}
        self.item_map = {}
        self.major_map = {}      # 专业映射
        self.category_map = {}   # 分类映射
        self.user_ids = None
        self.item_ids = None
        self.bias = 0.0
        self.user_bias = None
        self.item_bias = None
        self.major_factors = None      # 专业因子
        self.category_factors = None   # 分类因子
        self.is_trained = False

    def _build_maps(self):
        # 用户
        users = User.query.filter_by(role='user').all()
        self.user_ids = [u.id for u in users]
        self.user_map = {u: i for i, u in enumerate(self.user_ids)}
        # 图书
        books = Book.query.filter_by(status='active').all()
        self.item_ids = [b.id for b in books]
        self.item_map = {b: i for i, b in enumerate(self.item_ids)}
        # 专业
        majors = list(set(u.major for u in users if u.major))
        self.major_map = {m: i for i, m in enumerate(majors)}
        # 分类
        categories = list(set(b.category for b in books if b.category))
        self.category_map = {c: i for i, c in enumerate(categories)}
        print(f"特征映射: 用户 {len(self.user_ids)}, 图书 {len(self.item_ids)}, 专业 {len(majors)}, 分类 {len(categories)}")

    def _prepare_data(self, use_rating=True):
        if not self.user_map:
            self._build_maps()

        # 正样本
        positive = []
        if use_rating:
            ratings = Rating.query.all()
            for r in ratings:
                if r.user_id in self.user_map and r.book_id in self.item_map:
                    positive.append((r.user_id, r.book_id, r.rating))
        else:
            borrows = BorrowRecord.query.all()
            for b in borrows:
                if b.user_id in self.user_map and b.book_id in self.item_map:
                    positive.append((b.user_id, b.book_id, 1.0))

        if not positive:
            raise ValueError("无有效正样本！")

        # 负采样
        user_pos = defaultdict(list)
        for uid, bid, r in positive:
            user_pos[uid].append((bid, r))

        negative = []
        all_item_ids = set(self.item_map.keys())
        for uid, pos_list in user_pos.items():
            pos_books = {bid for bid, _ in pos_list}
            candidate_neg = list(all_item_ids - pos_books)
            neg_count = len(pos_list)
            if len(candidate_neg) < neg_count:
                continue
            sampled = random.sample(candidate_neg, neg_count)
            for bid in sampled:
                negative.append((uid, bid, 0.0))

        all_samples = positive + negative
        random.shuffle(all_samples)

        # 转换为索引，并收集特征
        data = []
        for uid, bid, label in all_samples:
            u_idx = self.user_map[uid]
            i_idx = self.item_map[bid]
            # 专业索引
            user = User.query.get(uid)
            major_idx = self.major_map.get(user.major, -1) if user else -1
            # 分类索引
            book = Book.query.get(bid)
            cat_idx = self.category_map.get(book.category, -1) if book else -1
            data.append((u_idx, i_idx, major_idx, cat_idx, label))

        return data

    def train(self, use_rating=True):
        data = self._prepare_data(use_rating)
        n_users = len(self.user_ids)
        n_items = len(self.item_ids)
        n_majors = len(self.major_map)
        n_cats = len(self.category_map)

        # 初始化参数（增加专业和分类的因子）
        self.bias = np.random.randn() * 0.1
        self.user_bias = np.random.randn(n_users) * 0.1
        self.item_bias = np.random.randn(n_items) * 0.1
        self.user_factors = np.random.normal(0, 0.1, (n_users, self.n_factors))
        self.item_factors = np.random.normal(0, 0.1, (n_items, self.n_factors))
        self.major_factors = np.random.normal(0, 0.1, (n_majors, self.n_factors)) if n_majors > 0 else None
        self.category_factors = np.random.normal(0, 0.1, (n_cats, self.n_factors)) if n_cats > 0 else None

        # 训练
        for epoch in range(self.n_epochs):
            np.random.shuffle(data)
            total_loss = 0
            for u_idx, i_idx, major_idx, cat_idx, r in data:
                # 预测
                pred = self.bias + self.user_bias[u_idx] + self.item_bias[i_idx]
                pred += np.dot(self.user_factors[u_idx], self.item_factors[i_idx])
                if major_idx != -1 and self.major_factors is not None:
                    pred += np.dot(self.user_factors[u_idx], self.major_factors[major_idx])
                    pred += np.dot(self.item_factors[i_idx], self.major_factors[major_idx])
                if cat_idx != -1 and self.category_factors is not None:
                    pred += np.dot(self.user_factors[u_idx], self.category_factors[cat_idx])
                    pred += np.dot(self.item_factors[i_idx], self.category_factors[cat_idx])
                err = r - pred
                total_loss += err ** 2

                # 更新
                self.bias += self.lr * err
                self.user_bias[u_idx] += self.lr * (err - self.reg * self.user_bias[u_idx])
                self.item_bias[i_idx] += self.lr * (err - self.reg * self.item_bias[i_idx])
                u_f = self.user_factors[u_idx]
                i_f = self.item_factors[i_idx]
                self.user_factors[u_idx] += self.lr * (err * i_f - self.reg * u_f)
                self.item_factors[i_idx] += self.lr * (err * u_f - self.reg * i_f)

                if major_idx != -1 and self.major_factors is not None:
                    m_f = self.major_factors[major_idx]
                    self.major_factors[major_idx] += self.lr * (err * (u_f + i_f) - self.reg * m_f)
                if cat_idx != -1 and self.category_factors is not None:
                    c_f = self.category_factors[cat_idx]
                    self.category_factors[cat_idx] += self.lr * (err * (u_f + i_f) - self.reg * c_f)

            if (epoch+1) % 10 == 0:
                print(f"Epoch {epoch+1}/{self.n_epochs}, loss: {total_loss/len(data):.4f}")

        self.is_trained = True
        print("FM模型训练完成")

    def predict(self, user_id, book_ids):
        if not self.is_trained:
            return {}
        if user_id not in self.user_map:
            return {}
        u_idx = self.user_map[user_id]
        preds = {}
        # 获取用户专业（如果存在）
        user = User.query.get(user_id)
        major_idx = self.major_map.get(user.major, -1) if user else -1
        for bid in book_ids:
            if bid not in self.item_map:
                continue
            i_idx = self.item_map[bid]
            book = Book.query.get(bid)
            cat_idx = self.category_map.get(book.category, -1) if book else -1
            # 计算预测值
            pred = self.bias + self.user_bias[u_idx] + self.item_bias[i_idx]
            pred += np.dot(self.user_factors[u_idx], self.item_factors[i_idx])
            if major_idx != -1 and self.major_factors is not None:
                pred += np.dot(self.user_factors[u_idx], self.major_factors[major_idx])
                pred += np.dot(self.item_factors[i_idx], self.major_factors[major_idx])
            if cat_idx != -1 and self.category_factors is not None:
                pred += np.dot(self.user_factors[u_idx], self.category_factors[cat_idx])
                pred += np.dot(self.item_factors[i_idx], self.category_factors[cat_idx])
            preds[bid] = float(pred)
        return preds

    def recommend(self, user_id, limit=10, exclude_ids=None):
        if exclude_ids is None:
            exclude_ids = []
        if not self.is_trained:
            return []

        exclude = set(exclude_ids)

        # 获取用户兴趣标签
        user = User.query.get(user_id)
        interest_tags = set()
        if user.interest_tags:
            interest_tags.update([t.strip() for t in user.interest_tags.split(',') if t.strip()])
        # 从借阅历史中补充标签（最近5本）
        for record in user.borrow_records.order_by(BorrowRecord.borrow_date.desc()).limit(5):
            if record.book and record.book.tags:
                interest_tags.update([t.strip() for t in record.book.tags.split(',') if t.strip()])

        # 候选图书：全量活跃图书
        candidate_books = Book.query.filter(
            Book.status == 'active',
            Book.id.notin_(exclude)
        ).all()

        # 兴趣过滤：如果用户有标签，则只保留标签有交集的图书
        if interest_tags:
            filtered_books = []
            for book in candidate_books:
                book_tags = set([t.strip() for t in book.tags.split(',') if t.strip()]) if book.tags else set()
                if book_tags & interest_tags:
                    filtered_books.append(book)
            # 如果过滤后不足，再放宽（这里直接保留所有，避免无推荐）
            if len(filtered_books) >= limit:
                candidate_books = filtered_books
            # 否则保留原候选集（或放宽阈值）

        candidate_ids = [b.id for b in candidate_books]
        predictions = self.predict(user_id, candidate_ids)
        sorted_items = sorted(predictions.items(), key=lambda x: x[1], reverse=True)
        rec_ids = [bid for bid, _ in sorted_items[:limit]]
        books = Book.query.filter(Book.id.in_(rec_ids)).all()
        book_dict = {b.id: b for b in books}
        return [book_dict[bid] for bid in rec_ids if bid in book_dict]


_fm_instance = None

def get_fm_recommender(force_retrain=False, use_rating=True):
    global _fm_instance
    if _fm_instance is None or force_retrain:
        _fm_instance = FMRecommender()
        _fm_instance.train(use_rating)
    return _fm_instance

def fm_recommend(user_id, limit=10, exclude_ids=None, use_rating=True):
    fm = get_fm_recommender(use_rating=use_rating)
    return fm.recommend(user_id, limit, exclude_ids)