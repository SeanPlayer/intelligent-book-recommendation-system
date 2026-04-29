
from collections import defaultdict
from datetime import datetime
import random
from app.models import BorrowRecord, User, Book, Rating
from .content_based import content_based_recommend
from .femf import femf_recommend
from .fm_recommender import fm_recommend
from .item_cf import item_cf_recommend
from .matrix_factorization import svd_recommend
from .popularity import get_hot_books
from .hybrid import get_personalized_recommendations


def split_data_by_time(ratio=0.8):
    """按时间划分训练/测试集，使用借阅记录的borrow_date作为时间戳"""
    # 获取所有有借阅记录的用户和图书
    records = []
    for borrow in BorrowRecord.query.all():
        records.append({
            'user_id': borrow.user_id,
            'book_id': borrow.book_id,
            'timestamp': borrow.borrow_date.timestamp(),
            'has_rating': bool(borrow.rating)  # 可选，标记是否有评分
        })

    if not records:
        raise ValueError("无交互记录，无法划分数据集！")

    # 按时间排序
    records.sort(key=lambda x: x['timestamp'])
    split_idx = int(len(records) * ratio)

    train_records = records[:split_idx]
    test_records = records[split_idx:]

    # 确保测试集中的用户/图书都在训练集中出现过
    train_user_ids = set(r['user_id'] for r in train_records)
    train_book_ids = set(r['book_id'] for r in train_records)

    test_records = [
        r for r in test_records
        if r['user_id'] in train_user_ids and r['book_id'] in train_book_ids
    ]

    # 构建字典
    train_dict = defaultdict(set)
    for r in train_records:
        train_dict[r['user_id']].add(r['book_id'])

    test_dict = defaultdict(set)
    for r in test_records:
        test_dict[r['user_id']].add(r['book_id'])

    print(f"训练集用户数：{len(train_dict)}, 测试集用户数：{len(test_dict)}")
    print(f"训练集图书数：{len(train_book_ids)}, 测试集图书数：{len(set(r['book_id'] for r in test_records))}")
    return train_dict, test_dict


def evaluate_algorithm(rec_func, train_dict, test_dict, top_n=10, sample_users=100):
    """评估推荐算法，随机采样用户，计算Precision/Recall/F1"""
    # 筛选出测试集中有交互的用户
    users = [u for u in test_dict.keys() if test_dict[u]]
    if not users:
        return 0.0, 0.0, 0.0

    # 随机采样
    if len(users) > sample_users:
        users = random.sample(users, sample_users)

    print(f"开始评估，共 {len(users)} 个用户...")
    total_hits = 0
    total_recommended = 0
    total_relevant = 0

    for uid in users:
        train_books = set(train_dict.get(uid, []))
        test_books = set(test_dict.get(uid, []))

        # 如果没有测试图书，跳过
        if not test_books:
            continue

        try:
            rec_books = rec_func(uid, limit=top_n, exclude_ids=list(train_books), use_rating=True)
        except Exception as e:
            print(f"用户 {uid} 推荐失败：{e}")
            rec_books = []

        rec_ids = [b.id for b in rec_books if hasattr(b, 'id')]
        hits = len(set(rec_ids) & test_books)

        total_hits += hits
        total_recommended += len(rec_ids)
        total_relevant += len(test_books)

    # 计算指标
    precision = total_hits / total_recommended if total_recommended > 0 else 0.0
    recall = total_hits / total_relevant if total_relevant > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return precision, recall, f1


def evaluate_all_algorithms(top_n=10, use_rating=True):
    print("开始数据划分...")
    train_dict, test_dict = split_data_by_time(ratio=0.8)

    algorithms = {
        '热门推荐': lambda uid, limit, exclude_ids, **kwargs: get_hot_books(limit, exclude_ids),
        '基于内容': lambda uid, limit, exclude_ids, **kwargs: content_based_recommend(uid, limit, exclude_ids),
        '物品协同过滤': lambda uid, limit, exclude_ids, **kwargs: item_cf_recommend(uid, limit, exclude_ids,
                                                                                    use_rating=use_rating),
        '矩阵分解': lambda uid, limit, exclude_ids, **kwargs: svd_recommend(uid, limit, exclude_ids,
                                                                            use_rating=use_rating),
        # 'FM模型': lambda uid, limit, exclude_ids, **kwargs: fm_recommend(uid, limit, exclude_ids,
        #                                                                  use_rating=kwargs.get('use_rating', True)),
        # '特征增强矩阵分解': lambda uid, limit, exclude_ids, **kwargs: femf_recommend(uid, limit, exclude_ids,
        #                                                                              use_rating=use_rating),
        '混合推荐': lambda uid, limit, exclude_ids, **kwargs: get_personalized_recommendations(
            User.query.get(uid), limit, exclude_ids, use_rating=use_rating
        )
    }

    results = {}
    for name, func in algorithms.items():
        try:
            p, r, f = evaluate_algorithm(func, train_dict, test_dict, top_n, sample_users=100)
            results[name] = {
                'precision': round(p, 4),
                'recall': round(r, 4),
                'f1': round(f, 4),
            }

            print(f"{name}: P={p:.4f}, R={r:.4f}, F1={f:.4f}")
        except Exception as e:
            results[name] = {'error': str(e)}
            print(f"{name} 评估失败: {e}")
    return results


