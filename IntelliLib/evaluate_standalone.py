import sys
import os


sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db
from app.models import User, Book, BorrowRecord, Rating
import random

# 导入所有推荐算法
from app.recommendation.popularity import get_hot_books
from app.recommendation.content_based import content_based_recommend
from app.recommendation.item_cf import item_cf_recommend
from app.recommendation.matrix_factorization import svd_recommend
from app.recommendation.fm_recommender import fm_recommend
from app.recommendation.hybrid import get_personalized_recommendations

# ==================== 配置 ====================
FIXED_USER_IDS = []  # 稍后自动填充
USE_RATING = True    # 是否使用评分
TOP_N = 10

# 算法适配器：将不同签名的函数统一为 (user_id, limit, exclude_ids) -> Book列表
def adapt_popularity(user_id, limit, exclude_ids):
    return get_hot_books(limit, exclude_ids)

def adapt_content(user_id, limit, exclude_ids):
    return content_based_recommend(user_id, limit, exclude_ids)

def adapt_itemcf(user_id, limit, exclude_ids):
    return item_cf_recommend(user_id, limit, exclude_ids, use_rating=USE_RATING)

def adapt_svd(user_id, limit, exclude_ids):
    return svd_recommend(user_id, limit, exclude_ids, use_rating=USE_RATING)

def adapt_fm(user_id, limit, exclude_ids):
    return fm_recommend(user_id, limit, exclude_ids, use_rating=USE_RATING)

def adapt_hybrid(user_id, limit, exclude_ids):
    return get_personalized_recommendations(
        User.query.get(user_id), limit, exclude_ids, strategy='auto', use_rating=USE_RATING
    )

# ALGORITHMS = {
#     '热门推荐': adapt_popularity,
#     '基于内容': adapt_content,
#     '物品协同过滤': adapt_itemcf,
#     '矩阵分解': adapt_svd,
#     # 'FM模型': adapt_fm,
#     '混合推荐': adapt_hybrid,
# }
ALGORITHMS = {
    '热门推荐': lambda uid, limit, exclude_ids: get_hot_books(limit, exclude_ids),
    '基于内容': lambda uid, limit, exclude_ids: content_based_recommend(uid, limit, exclude_ids),
    '物品协同过滤': lambda uid, limit, exclude_ids: item_cf_recommend(uid, limit, exclude_ids, use_rating=USE_RATING),
    # 'FM模型': lambda uid, limit, exclude_ids: fm_recommend(uid, limit, exclude_ids, use_rating=USE_RATING),
    '混合推荐': lambda uid, limit, exclude_ids: get_personalized_recommendations(
        User.query.get(uid), limit, exclude_ids, use_rating=USE_RATING
    )
}

# ==================== 辅助函数 ====================
def get_fixed_users(num=3):
    """获取有借阅历史的固定用户"""
    users = User.query.filter(User.role == 'user').limit(50).all()
    valid = []
    for u in users:
        if BorrowRecord.query.filter_by(user_id=u.id).count() > 0:
            valid.append(u.id)
    if len(valid) < num:
        return valid
    return random.sample(valid, num)

def get_test_books_for_user(user_id, ratio=0.2):
    """获取用户测试集图书（最后20%的借阅记录）"""
    records = BorrowRecord.query.filter_by(user_id=user_id).order_by(BorrowRecord.borrow_date).all()
    book_ids = [r.book_id for r in records]
    split = int(len(book_ids) * (1 - ratio))
    return set(book_ids[split:])

def evaluate_user(user_id, algorithm_func, train_exclude):
    """对单个用户评估算法：返回推荐列表和命中情况"""
    rec_books = algorithm_func(user_id, limit=TOP_N, exclude_ids=train_exclude)
    rec_ids = [b.id for b in rec_books]
    test_books = get_test_books_for_user(user_id)
    hits = set(rec_ids) & test_books
    return rec_ids, hits, test_books

def main():
    app = create_app()
    with app.app_context():
        # 1. 选择固定用户
        fixed_users = get_fixed_users(num=3)
        print(f"固定评估用户: {fixed_users}\n")

        # 2. 对每个用户，获取训练集排除列表（用户历史中除最后20%外的所有图书）
        train_exclude = {}
        for uid in fixed_users:
            all_borrow = [r.book_id for r in BorrowRecord.query.filter_by(user_id=uid).order_by(BorrowRecord.borrow_date).all()]
            test_books = get_test_books_for_user(uid)
            train_exclude[uid] = [bid for bid in all_borrow if bid not in test_books]

        # 3. 对每个算法，打印对每个用户的推荐结果和命中情况
        for algo_name, algo_func in ALGORITHMS.items():
            print(f"\n{'='*60}")
            print(f"算法: {algo_name}")
            print('='*60)
            total_hits = 0
            total_recommended = 0
            total_relevant = 0
            for uid in fixed_users:
                rec_ids, hits, test_books = evaluate_user(uid, algo_func, train_exclude[uid])
                print(f"\n用户 {uid}:")
                print(f"  推荐图书ID: {rec_ids[:5]}{'...' if len(rec_ids)>5 else ''}")
                print(f"  命中测试集图书: {hits}")
                print(f"  测试集图书: {test_books}")
                total_hits += len(hits)
                total_recommended += len(rec_ids)
                total_relevant += len(test_books)
            # 计算该算法在固定用户上的平均指标
            precision = total_hits / total_recommended if total_recommended else 0
            recall = total_hits / total_relevant if total_relevant else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision+recall) else 0
            print(f"\n--- 用户 {fixed_users} 汇总 ---")
            print(f"准确率: {precision:.2%}  召回率: {recall:.2%}  F1: {f1:.2%}")
        print("\n评估完成")

if __name__ == '__main__':
    main()