"""
基于物品的协同过滤（改进版：皮尔逊相似度 + 热门惩罚）
"""
import numpy as np
from collections import defaultdict
from app.models import BorrowRecord, Rating, Book
from .utils import build_user_item_matrix

class ItemCF:
    def __init__(self):
        self.sim_matrix = None
        self.book_ids = None
        self.book_index = {}

    def _pearson_sim(self, users_i, users_j):
        """计算两个物品的皮尔逊相似度（基于共同用户）"""
        common = set(users_i.keys()) & set(users_j.keys())
        if len(common) < 2:
            return 0.0
        # 均值
        mean_i = np.mean([users_i[u] for u in common])
        mean_j = np.mean([users_j[u] for u in common])
        numerator = sum((users_i[u] - mean_i) * (users_j[u] - mean_j) for u in common)
        denom_i = np.sqrt(sum((users_i[u] - mean_i) ** 2 for u in common))
        denom_j = np.sqrt(sum((users_j[u] - mean_j) ** 2 for u in common))
        if denom_i == 0 or denom_j == 0:
            return 0.0
        return numerator / (denom_i * denom_j)

    def train(self, user_items=None, use_rating=True):
        if user_items is None:
            user_items = build_user_item_matrix(use_rating=use_rating)
        # 收集所有图书
        all_books = set()
        for items in user_items.values():
            all_books.update(items.keys())
        self.book_ids = sorted(all_books)
        self.book_index = {bid: idx for idx, bid in enumerate(self.book_ids)}
        n_books = len(self.book_ids)

        # 构建图书-用户倒排表（仅记录哪些用户借阅过）
        book_users = defaultdict(set)
        for uid, items in user_items.items():
            for bid in items:
                book_users[bid].add(uid)

        # 计算物品相似度（Jaccard相似度）
        sim = np.zeros((n_books, n_books))
        for i in range(n_books):
            bid_i = self.book_ids[i]
            users_i = book_users.get(bid_i, set())
            if not users_i:
                continue
            for j in range(i + 1, n_books):
                bid_j = self.book_ids[j]
                users_j = book_users.get(bid_j, set())
                if not users_j:
                    continue
                common = len(users_i & users_j)
                union = len(users_i | users_j)
                if union > 0:
                    sim[i, j] = common / union
                    sim[j, i] = sim[i, j]
        self.sim_matrix = sim

    def recommend(self, user_id, limit=10, exclude_ids=None, user_items=None, use_rating=True):
        if self.sim_matrix is None:
            self.train(use_rating=use_rating)
        if exclude_ids is None:
            exclude_ids = []
        # 使用传入的 user_items，如果没有则从数据库构建
        if user_items is None:
            user_items = build_user_item_matrix(use_rating=use_rating)
        user_vec = user_items.get(user_id, {})
        if not user_vec:
            return []

        exclude = set(exclude_ids)  # 只排除传入的 ID，不再排除 user_vec 中的书
        scores = defaultdict(float)
        for bid, weight in user_vec.items():
            if bid not in self.book_index:
                continue
            idx = self.book_index[bid]
            sim_row = self.sim_matrix[idx]
            for j, sim_val in enumerate(sim_row):
                if sim_val == 0:
                    continue
                other_bid = self.book_ids[j]
                if other_bid in exclude:
                    continue
                scores[other_bid] += weight * sim_val

        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        rec_ids = [bid for bid, _ in sorted_items[:limit]]

        if len(rec_ids) < limit:
            from .popularity import get_hot_books
            hot_books = get_hot_books(limit - len(rec_ids), exclude_ids)
            rec_ids.extend([b.id for b in hot_books if b.id not in rec_ids])

        books = Book.query.filter(Book.id.in_(rec_ids)).all()
        book_dict = {b.id: b for b in books}
        return [book_dict[bid] for bid in rec_ids if bid in book_dict]

_item_cf_instance = None

def get_item_cf(force_retrain=False, use_rating=True):
    global _item_cf_instance
    if _item_cf_instance is None or force_retrain:
        _item_cf_instance = ItemCF()
        _item_cf_instance.train(use_rating=use_rating)
    return _item_cf_instance

def item_cf_recommend(user_id, limit=10, exclude_ids=None, use_rating=True):
    cf = get_item_cf(use_rating=use_rating)
    return cf.recommend(user_id, limit, exclude_ids, use_rating=use_rating)
