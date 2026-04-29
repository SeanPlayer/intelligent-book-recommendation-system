"""
FunkSVD 矩阵分解，利用评分和借阅作为隐式反馈
"""
import numpy as np
from .utils import build_user_item_matrix

class FunkSVD:
    def __init__(self, n_factors=50, learning_rate=0.005, reg=0.02, n_epochs=50):
        self.n_factors = n_factors
        self.lr = learning_rate
        self.reg = reg
        self.n_epochs = n_epochs
        self.user_factors = None
        self.item_factors = None
        self.user_map = {}
        self.item_map = {}
        self.user_ids = None
        self.item_ids = None

    def fit(self, user_items):
        """
        user_items: dict {user_id: {book_id: weight}}，weight可以是评分或隐式权重
        """
        # 获取所有用户和物品
        users = sorted(user_items.keys())
        items = set()
        for u, ib in user_items.items():
            items.update(ib.keys())
        items = sorted(items)
        self.user_map = {uid: idx for idx, uid in enumerate(users)}
        self.item_map = {iid: idx for idx, iid in enumerate(items)}
        self.user_ids = users
        self.item_ids = items
        n_users = len(users)
        n_items = len(items)

        # 初始化
        self.user_factors = np.random.normal(0, 0.1, (n_users, self.n_factors))
        self.item_factors = np.random.normal(0, 0.1, (n_items, self.n_factors))

        # 构建训练数据
        data = []
        for u, items_dict in user_items.items():
            u_idx = self.user_map[u]
            for i, w in items_dict.items():
                i_idx = self.item_map[i]
                data.append((u_idx, i_idx, w))

        losses = []
        # SGD训练
        for epoch in range(self.n_epochs):
            np.random.shuffle(data)
            total_loss = 0
            for u_idx, i_idx, r in data:
                pred = np.dot(self.user_factors[u_idx], self.item_factors[i_idx])
                err = r - pred
                # 更新
                self.user_factors[u_idx] += self.lr * (err * self.item_factors[i_idx] - self.reg * self.user_factors[u_idx])
                self.item_factors[i_idx] += self.lr * (err * self.user_factors[u_idx] - self.reg * self.item_factors[i_idx])
                total_loss += err**2
            avg_loss = total_loss / len(data)
            losses.append(avg_loss)
            if (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch + 1}/{self.n_epochs}, loss: {avg_loss:.4f}")
        # print("\n训练损失记录（每10轮）:")
        # print("轮次\t训练损失")
        # for i in range(0, self.n_epochs, 10):
        #     print(f"{i + 1}\t{losses[i]:.4f}")

    def predict(self, user_id, item_id):
        if user_id not in self.user_map or item_id not in self.item_map:
            return 0
        u = self.user_map[user_id]
        i = self.item_map[item_id]
        return np.dot(self.user_factors[u], self.item_factors[i])

    def recommend(self, user_id, exclude_ids=None, top_n=10):
        if user_id not in self.user_map:
            return []
        u = self.user_map[user_id]
        scores = np.dot(self.user_factors[u], self.item_factors.T)
        item_indices = np.argsort(-scores)
        if exclude_ids is None:
            exclude_ids = []
        exclude_idxs = {self.item_map[iid] for iid in exclude_ids if iid in self.item_map}
        rec_ids = []
        for idx in item_indices:
            if len(rec_ids) >= top_n:
                break
            if idx not in exclude_idxs:
                rec_ids.append(self.item_ids[idx])
        return rec_ids


_svd_model = None
def get_svd_model(force_retrain=False, use_rating=True):
    global _svd_model
    if _svd_model is None or force_retrain:
        user_items = build_user_item_matrix(use_rating=use_rating)
        svd = FunkSVD(n_factors=100, n_epochs=150, learning_rate=0.003, reg=0.01)  # 增加因子和迭代，降低学习率
        svd.fit(user_items)
        _svd_model = svd
    return _svd_model


def svd_recommend(user_id, limit=10, exclude_ids=None, use_rating=True):
    model = get_svd_model(use_rating=use_rating)
    if model is None:
        return []
    rec_ids = model.recommend(user_id, exclude_ids=exclude_ids, top_n=limit)
    from app.models import Book
    books = Book.query.filter(Book.id.in_(rec_ids)).all()
    book_dict = {b.id: b for b in books}
    return [book_dict[bid] for bid in rec_ids if bid in book_dict]
