"""
混合推荐器：组合多种推荐策略，并实现去重、曝光降权等功能
"""
from app.models import User, Book, Exposure
from .popularity import get_hot_books
from .content_based import content_based_recommend
from .item_cf import item_cf_recommend
from .matrix_factorization import svd_recommend
import random
from datetime import datetime, timedelta


def get_personalized_recommendations(user, limit=10, exclude_ids=None, use_rating=True):
    if exclude_ids is None:
        exclude_ids = []
    if user.is_admin():
        return []

    # 获取各算法的推荐结果（按顺序）
    # 矩阵分解权重较高但候选数减少，以平衡影响力
    svd_books = svd_recommend(user.id, limit * 2, exclude_ids, use_rating)   # 只取前20本
    itemcf_books = item_cf_recommend(user.id, limit * 3, exclude_ids, use_rating)  # 取前30本
    content_books = content_based_recommend(user.id, limit * 3, exclude_ids)       # 取前30本

    # 合并打分（位置赋分法）
    scores = {}

    def add_scores(book_list, weight):
        for idx, book in enumerate(book_list):
            # 动态计算最大可能得分，确保各算法公平
            max_score = len(book_list)
            score = (max_score - idx) * weight
            scores[book.id] = scores.get(book.id, 0) + score

    # 权重：SVD 0.4, ItemCF 0.35, Content 0.25
    add_scores(svd_books, 0.4)
    add_scores(itemcf_books, 0.35)
    add_scores(content_books, 0.25)

    # 按分数排序，取前limit
    sorted_books = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    rec_ids = [bid for bid, _ in sorted_books[:limit]]

    # 如果不足，用热门补充
    if len(rec_ids) < limit:
        hot = get_hot_books(limit - len(rec_ids), exclude_ids)
        rec_ids.extend([b.id for b in hot if b.id not in rec_ids])

    # 查询图书对象
    books = Book.query.filter(Book.id.in_(rec_ids)).all()
    book_dict = {b.id: b for b in books}
    result = [book_dict[bid] for bid in rec_ids if bid in book_dict]

    # 应用曝光降权：将近期曝光过的书排到后面
    result = apply_exposure_penalty(user.id, result)

    return result


def apply_exposure_penalty(user_id, books, decay_hours=24, penalty_factor=0.5):
    """
    对图书列表应用曝光惩罚：近期曝光过的书分数降低
    """
    since = datetime.utcnow() - timedelta(hours=decay_hours)
    exposures = Exposure.query.filter(
        Exposure.user_id == user_id,
        Exposure.expose_time >= since
    ).all()
    exposed_book_ids = {exp.book_id for exp in exposures}

    if not exposed_book_ids:
        return books

    unexposed = [b for b in books if b.id not in exposed_book_ids]
    exposed = [b for b in books if b.id in exposed_book_ids]

    random.shuffle(exposed)
    return unexposed + exposed


def rerank_with_user_actions(user, books, limit):
    """根据用户点击和负面反馈重排"""
    from app.models import UserAction
    week_ago = datetime.utcnow() - timedelta(days=7)
    clicks = UserAction.query.filter_by(
        user_id=user.id, action_type='click'
    ).filter(UserAction.created_at >= week_ago).all()
    clicked_book_ids = [a.book_id for a in clicks]

    day_ago = datetime.utcnow() - timedelta(days=1)
    negatives = UserAction.query.filter_by(
        user_id=user.id, action_type='refresh_negative'
    ).filter(UserAction.created_at >= day_ago).all()
    negative_book_ids = [a.book_id for a in negatives]

    if not clicked_book_ids and not negative_book_ids:
        return books[:limit]

    scored = []
    for book in books:
        score = 1.0
        if clicked_book_ids:
            book_tags = set(book.tags.split(',')) if book.tags else set()
            if book_tags:
                for cid in clicked_book_ids:
                    cbook = Book.query.get(cid)
                    if cbook and cbook.tags:
                        ctags = set(cbook.tags.split(','))
                        overlap = len(book_tags & ctags)
                        if overlap > 0:
                            score += overlap * 0.2
        if negative_book_ids:
            book_tags = set(book.tags.split(',')) if book.tags else set()
            if book_tags:
                for nid in negative_book_ids:
                    nbook = Book.query.get(nid)
                    if nbook and nbook.tags:
                        ntags = set(nbook.tags.split(','))
                        overlap = len(book_tags & ntags)
                        if overlap > 0:
                            score -= overlap * 0.3
        scored.append((book, max(score, 0.1)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [book for book, _ in scored[:limit]]
