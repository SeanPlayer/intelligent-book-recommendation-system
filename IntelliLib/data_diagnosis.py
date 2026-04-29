# data_diagnosis.py
from app import create_app, db
from app.models import User, Book, BorrowRecord, Rating

app = create_app()
with app.app_context():
    # 1. 用户统计
    print(f"用户数: {User.query.filter_by(role='user').count()}")
    # 2. 图书统计
    print(f"活跃图书数: {Book.query.filter_by(status='active').count()}")
    # 3. 借阅记录统计
    borrows = BorrowRecord.query.all()
    print(f"借阅记录数: {len(borrows)}")
    # 4. 评分记录统计
    ratings = Rating.query.all()
    print(f"评分记录数: {len(ratings)}")
    # 5. 检查借阅记录是否覆盖图书和用户
    book_ids_in_borrow = set(b.book_id for b in borrows)
    print(f"借阅记录中图书数: {len(book_ids_in_borrow)}")
    # 6. 检查测试集划分（按时间）
    from app.recommendation.evaluation import split_data_by_time
    train, test = split_data_by_time(0.8)
    train_users = set(train.keys())
    test_users = set(test.keys())
    train_books = set()
    for books in train.values():
        train_books.update(books)
    test_books = set()
    for books in test.values():
        test_books.update(books)
    print(f"训练集用户数: {len(train_users)}, 测试集用户数: {len(test_users)}")
    print(f"训练集图书数: {len(train_books)}, 测试集图书数: {len(test_books)}")
    # 7. 检查交集
    common_users = train_users & test_users
    common_books = train_books & test_books
    print(f"共同用户数: {len(common_users)}")
    print(f"共同图书数: {len(common_books)}")
    if not common_books:
        print("⚠️ 严重问题：训练集和测试集没有共同图书，推荐永远无法命中！")