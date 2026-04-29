"""
特征增强矩阵分解 (FEMF)
在标准矩阵分解中加入用户专业和图书分类的隐向量
"""
import numpy as np
from collections import defaultdict
from app.models import User, Book, Rating, BorrowRecord
from .utils import build_user_item_matrix

class FEMF:
    def __init__(self, n_factors=50, learning_rate=0.005, reg=0.02, n_epochs=50):
        self.n_factors = n_factors
        self.lr = learning_rate
        self.reg = reg
        self.n_epochs = n_epochs
        # 基础因子
        self.user_factors = None
        self.item_factors = None
        # 专业因子（用户）
        self.major_factors = None
        # 分类因子（图书）
        self.cat_factors = None
        # 映射
        self.user_map = {}
        self.item_map = {}
        self.major_map = {}
        self.cat_map = {}
        self.user_ids = None
        self.item_ids = None
        self.major_ids = None
        self.cat_ids = None

    def _build_maps(self):
        users = User.query.filter_by(role='user').all()
        books = Book.query.filter_by(status='active').all()
        self.user_ids = [u.id for u in users]
        self.item_ids = [b.id for b in books]
        self.user_map = {u: i for i, u in enumerate(self.user_ids)}
        self.item_map = {b: i for i, b in enumerate(self.item_ids)}

        # 专业映射
        majors = list(set(u.major for u in users if u.major))
        self.major_ids = majors
        self.major_map = {m: i for i, m in enumerate(majors)}

        # 分类映射
        cats = list(set(b.category for b in books if b.category))
        self.cat_ids = cats
        self.cat_map = {c: i for i, c in enumerate(cats)}

        print(f"[FEMF] 构建映射: 用户 {len(self.user_ids)}, 图书 {len(self.item_ids)}, 专业 {len(majors)}, 分类 {len(cats)}")

    def _prepare_data(self, use_rating=True):
        if not self.user_map:
            self._build_maps()

        data = []
        if use_rating:
            for r in Rating.query.all():
                if r.user_id in self.user_map and r.book_id in self.item_map:
                    u = self.user_map[r.user_id]
                    i = self.item_map[r.book_id]
                    user = User.query.get(r.user_id)
                    major_idx = self.major_map.get(user.major, -1) if user else -1
                    book = Book.query.get(r.book_id)
                    cat_idx = self.cat_map.get(book.category, -1) if book else -1
                    data.append((u, i, major_idx, cat_idx, r.rating))
        else:
            for b in BorrowRecord.query.all():
                if b.user_id in self.user_map and b.book_id in self.item_map:
                    u = self.user_map[b.user_id]
                    i = self.item_map[b.book_id]
                    user = User.query.get(b.user_id)
                    major_idx = self.major_map.get(user.major, -1) if user else -1
                    book = Book.query.get(b.book_id)
                    cat_idx = self.cat_map.get(book.category, -1) if book else -1
                    data.append((u, i, major_idx, cat_idx, 1.0))
        print(f"[FEMF] 准备训练数据: {len(data)} 条样本")
        return data

    def train(self, use_rating=True):
        data = self._prepare_data(use_rating)
        n_users = len(self.user_ids)
        n_items = len(self.item_ids)
        n_majors = len(self.major_ids)
        n_cats = len(self.cat_ids)

        # 初始化因子
        self.user_factors = np.random.normal(0, 0.1, (n_users, self.n_factors))
        self.item_factors = np.random.normal(0, 0.1, (n_items, self.n_factors))
        self.major_factors = np.random.normal(0, 0.1, (n_majors, self.n_factors)) if n_majors > 0 else None
        self.cat_factors = np.random.normal(0, 0.1, (n_cats, self.n_factors)) if n_cats > 0 else None

        for epoch in range(self.n_epochs):
            np.random.shuffle(data)
            total_loss = 0
            for u, i, m_idx, c_idx, r in data:
                # 构造用户向量
                u_vec = self.user_factors[u].copy()
                if m_idx != -1 and self.major_factors is not None:
                    u_vec += self.major_factors[m_idx]

                # 构造物品向量
                i_vec = self.item_factors[i].copy()
                if c_idx != -1 and self.cat_factors is not None:
                    i_vec += self.cat_factors[c_idx]

                pred = np.dot(u_vec, i_vec)
                err = r - pred
                total_loss += err**2

                # 更新基础因子
                self.user_factors[u] += self.lr * (err * i_vec - self.reg * self.user_factors[u])
                self.item_factors[i] += self.lr * (err * u_vec - self.reg * self.item_factors[i])

                # 更新专业因子
                if m_idx != -1 and self.major_factors is not None:
                    self.major_factors[m_idx] += self.lr * (err * i_vec - self.reg * self.major_factors[m_idx])

                # 更新分类因子
                if c_idx != -1 and self.cat_factors is not None:
                    self.cat_factors[c_idx] += self.lr * (err * u_vec - self.reg * self.cat_factors[c_idx])

            if (epoch+1) % 10 == 0:
                print(f"[FEMF] Epoch {epoch+1}/{self.n_epochs}, loss: {total_loss/len(data):.4f}")

    def _get_user_vector(self, user_id):
        """获取用户最终向量（基础+专业）"""
        if user_id not in self.user_map:
            return None
        u = self.user_map[user_id]
        vec = self.user_factors[u].copy()
        user = User.query.get(user_id)
        if user and user.major in self.major_map:
            m_idx = self.major_map[user.major]
            vec += self.major_factors[m_idx]
        return vec

    def _get_item_vector(self, book_id):
        """获取图书最终向量（基础+分类）"""
        if book_id not in self.item_map:
            return None
        i = self.item_map[book_id]
        vec = self.item_factors[i].copy()
        book = Book.query.get(book_id)
        if book and book.category in self.cat_map:
            c_idx = self.cat_map[book.category]
            vec += self.cat_factors[c_idx]
        return vec

    def predict(self, user_id, item_ids):
        if self.user_factors is None:
            return {}
        u_vec = self._get_user_vector(user_id)
        if u_vec is None:
            return {}
        scores = {}
        for bid in item_ids:
            i_vec = self._get_item_vector(bid)
            if i_vec is not None:
                scores[bid] = float(np.dot(u_vec, i_vec))
        return scores

    def recommend(self, user_id, limit=10, exclude_ids=None):
        if exclude_ids is None:
            exclude_ids = []
        if self.user_factors is None:
            self.train()
        if user_id not in self.user_map:
            return []

        exclude = set(exclude_ids)

        # 获取用户兴趣标签（同上）
        user = User.query.get(user_id)
        interest_tags = set()
        if user.interest_tags:
            interest_tags.update([t.strip() for t in user.interest_tags.split(',') if t.strip()])
        for record in user.borrow_records.order_by(BorrowRecord.borrow_date.desc()).limit(5):
            if record.book and record.book.tags:
                interest_tags.update([t.strip() for t in record.book.tags.split(',') if t.strip()])

        candidate_books = Book.query.filter(
            Book.status == 'active',
            Book.id.notin_(exclude)
        ).all()

        if interest_tags:
            filtered_books = []
            for book in candidate_books:
                book_tags = set([t.strip() for t in book.tags.split(',') if t.strip()]) if book.tags else set()
                if book_tags & interest_tags:
                    filtered_books.append(book)
            if len(filtered_books) >= limit:
                candidate_books = filtered_books

        candidate_ids = [b.id for b in candidate_books]
        predictions = self.predict(user_id, candidate_ids)
        if not predictions:
            return []
        sorted_items = sorted(predictions.items(), key=lambda x: x[1], reverse=True)
        rec_ids = [bid for bid, _ in sorted_items[:limit]]
        books = Book.query.filter(Book.id.in_(rec_ids)).all()
        book_dict = {b.id: b for b in books}
        return [book_dict[bid] for bid in rec_ids if bid in book_dict]


_femf_instance = None

def get_femf(force_retrain=False, use_rating=True):
    global _femf_instance
    if _femf_instance is None or force_retrain:
        _femf_instance = FEMF(n_factors=50, learning_rate=0.005, reg=0.02, n_epochs=50)
        _femf_instance.train(use_rating)
    return _femf_instance

def femf_recommend(user_id, limit=10, exclude_ids=None, use_rating=True):
    femf = get_femf(use_rating=use_rating)
    return femf.recommend(user_id, limit, exclude_ids)