# inspect_recommendations.py
import sys
import os

from app.recommendation.femf import femf_recommend
from app.recommendation.fm_recommender import fm_recommend, get_fm_recommender

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import create_app
from app.models import User, Book, BorrowRecord, Rating
from app.recommendation.matrix_factorization import svd_recommend
from app.recommendation.content_based import content_based_recommend, ContentBasedRecommender  # 新增导入
from app.recommendation.evaluation import split_data_by_time
from app.recommendation.item_cf import item_cf_recommend


def main():
    app = create_app()
    with app.app_context():
        train_dict, test_dict = split_data_by_time(ratio=0.8)
        sample_users = list(test_dict.keys())[:3]  # 取前3个
        for uid in sample_users:
            print(f"\n{'=' * 60}")
            print(f"用户 ID: {uid}")
            user = User.query.get(uid)
            print(f"用户名: {user.username}, 专业: {user.major}, 兴趣标签: {user.interest_tags}")
            train_books = train_dict.get(uid, set())
            test_books = test_dict.get(uid, set())
            print(f"训练集图书数: {len(train_books)}")
            print(f"测试集图书数: {len(test_books)}")

            if train_books:
                print("\n训练集图书（用户已借阅的书）:")
                for bid in list(train_books)[:5]:
                    book = Book.query.get(bid)
                    print(f"  {bid}: {book.title}（{book.category}，标签: {book.tags}）")
            if test_books:
                print("\n测试集图书（用户未来会借阅的书）:")
                for bid in test_books:
                    book = Book.query.get(bid)
                    print(f"  {bid}: {book.title}（{book.category}，标签: {book.tags}）")
            else:
                print("\n测试集为空")

            # 矩阵分解
            svd_recs = svd_recommend(uid, limit=10, exclude_ids=list(train_books))
            print("\n矩阵分解推荐（前5本）:")
            for i, book in enumerate(svd_recs[:5]):
                print(f"  {book.id}: {book.title}（{book.category}，标签: {book.tags}）")

            # 内容推荐
            cb_recs = content_based_recommend(uid, limit=10, exclude_ids=list(train_books))
            print("\n基于内容推荐（前5本）:")
            if cb_recs:
                for i, book in enumerate(cb_recs[:5]):
                    print(f"  {book.id}: {book.title}（{book.category}，标签: {book.tags}）")
            else:
                print("  无推荐结果")

            # 协同过滤
            user_items = {}
            for uid, books_set in train_dict.items():
                user_items[uid] = {bid: 1 for bid in books_set}  # 权重为1
            icf_recs = item_cf_recommend(uid, limit=10, exclude_ids=list(train_books))
            print("\n物品协同过滤推荐（前5本）:")
            if icf_recs:
                for i, book in enumerate(icf_recs[:5]):
                    print(f"  {book.id}: {book.title}（{book.category}，标签: {book.tags}）")
            else:
                print("  无推荐结果")

            # FEMF-特征增强矩阵分解
            femf_recs = femf_recommend(uid, limit=10, exclude_ids=list(train_books), use_rating=True)
            print("\nFEMF推荐（前5本）:")
            if femf_recs:
                for i, book in enumerate(femf_recs[:5]):
                    print(f"  {book.id}: {book.title}（{book.category}，标签: {book.tags}）")
            else:
                print("  无推荐结果")

            # FM模型
            fm_recs = fm_recommend(uid, limit=10, exclude_ids=list(train_books), use_rating=True)
            print("\nFM模型推荐（前5本）:")
            if fm_recs:
                for i, book in enumerate(fm_recs[:5]):
                    print(f"  {book.id}: {book.title}（{book.category}，标签: {book.tags}）")
            else:
                print("  无推荐结果")
            # 获取FM模型并预测测试集图书的分数
            fm_model = get_fm_recommender(use_rating=True)
            test_scores = fm_model.predict(uid, list(test_books))
            print("测试集图书FM预测分数:")
            for bid in test_books:
                score = test_scores.get(bid, 0)
                print(f"  {bid}: {score:.4f}")

            # 对比命中情况
            svd_hits = set([b.id for b in svd_recs]) & test_books
            cb_hits = set([b.id for b in cb_recs]) & test_books if cb_recs else set()
            icf_hits = set([b.id for b in icf_recs]) & test_books if icf_recs else set()
            fm_hits = set([b.id for b in fm_recs]) & test_books if fm_recs else set()
            femf_hits = set([b.id for b in femf_recs]) & test_books if femf_recs else set()

            print(f"\n矩阵分解命中测试集: {svd_hits}")
            print(f"基于内容命中测试集: {cb_hits}")
            print(f"物品协同过滤命中测试集: {icf_hits}")
            print(f"FEMF命中测试集: {femf_hits}")
            print(f"FM模型命中测试集: {fm_hits}")
        # 手动计算用户21的兴趣标签与测试集图书的相似度
        if uid == 21:
            from app.recommendation.content_based import _content_instance
            if _content_instance is None:
                _content_instance = ContentBasedRecommender()
                _content_instance.train()
            user = User.query.get(21)
            user_tags = _content_instance._get_user_interest_tags(user)
            print(f"用户21的user_tags: {user_tags}")
            for bid in [200, 25, 402]:
                book = Book.query.get(bid)
                if book and book.tags:
                    book_tags = set([t.strip() for t in book.tags.split(',') if t.strip()])
                    intersection = len(user_tags & book_tags)
                    union = len(user_tags | book_tags)
                    sim = intersection / union if union > 0 else 0
                    print(f"  书{bid} {book.title}: 交集={intersection}, 并集={union}, sim={sim:.4f}")

if __name__ == '__main__':
    main()