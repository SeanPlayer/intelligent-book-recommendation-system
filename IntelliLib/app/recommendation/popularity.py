
from app.models import Book, CreditConfig, BorrowRecord

def get_hot_books(limit=10, exclude_ids=None):
    """
    获取热门图书，按借阅次数和评分综合排序
    :param limit: 返回数量
    :param exclude_ids: 要排除的图书ID列表
    :return: Book对象列表
    """
    if exclude_ids is None:
        exclude_ids = []

    query = Book.query.filter_by(status='active')
    if exclude_ids:
        query = query.filter(Book.id.notin_(exclude_ids))
    books = query.all()

    # 计算热度分数：借阅次数权重0.6，评分权重0.4（评分归一化到0-5，乘以20后与借阅次数相当）
    scored = []
    for book in books:
        borrow_score = book.borrow_count or 0
        rating_score = (book.average_rating or 0) * 20
        hot_score = borrow_score * 0.6 + rating_score * 0.4
        scored.append((book, hot_score))

    # 按分数降序排序，取前limit
    scored.sort(key=lambda x: x[1], reverse=True)
    return [book for book, _ in scored[:limit]]



# from app.models import Book, BorrowRecord
# from sqlalchemy import func
#
# def get_hot_books(limit=10, exclude_ids=None):
#     """
#     基于借阅次数排序的热门图书
#     :param exclude_ids: 要排除的图书ID列表
#     """
#     if exclude_ids is None:
#         exclude_ids = []
#     query = Book.query.filter_by(status='active')
#     if exclude_ids:
#         query = query.filter(Book.id.notin_(exclude_ids))
#     # 按借阅次数降序
#     return query.order_by(Book.borrow_count.desc()).limit(limit).all()

