from collections import defaultdict
from app.models import BorrowRecord, Rating

def build_user_item_matrix(use_rating=True):
    """
    构建用户-物品交互矩阵
    :param use_rating: 如果为 True，权重使用评分（如果存在），否则用 1
    """
    user_items = defaultdict(dict)
    records = BorrowRecord.query.all()
    for r in records:
        weight = 1
        if use_rating and r.rating:
            weight = r.rating
        # 如果同一用户对同一本书有多条记录（不同时间），取最大权重
        if r.book_id in user_items[r.user_id]:
            user_items[r.user_id][r.book_id] = max(user_items[r.user_id][r.book_id], weight)
        else:
            user_items[r.user_id][r.book_id] = weight
    return user_items

def get_user_interacted_books(user_id):
    """获取用户借阅过的图书ID集合（包括评分过的，但评分可能无借阅？这里统一用借阅）"""
    from app.models import BorrowRecord
    records = BorrowRecord.query.filter_by(user_id=user_id).all()
    return {r.book_id for r in records}
