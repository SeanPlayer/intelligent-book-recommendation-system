# """
# 图书测试数据生成
# 生成具有不同类别和特征的测试图书
# """
#
# import random
# from faker import Faker
# from app import db
# from app.models import Book
# from .base_data import BOOK_CATEGORIES, POPULAR_TAGS, FEATURED_BOOKS
#
# class BookDataGenerator:
#     """图书数据生成器"""
#
#     def __init__(self):
#         self.fake = Faker('zh_CN')
#
#     def create_featured_books(self):
#         """创建/更新预定义的特征图书"""
#         print("📚 创建/更新特征图书...")
#         books = []
#
#         for book_data in FEATURED_BOOKS:
#             # 按ISBN检查图书是否存在
#             existing_book = Book.query.filter_by(isbn=book_data['isbn']).first()
#
#             if existing_book:
#                 print(f"🔄 更新图书: {existing_book.title}")
#                 # 更新图书信息
#                 existing_book.title = book_data['title']
#                 existing_book.author = book_data['author']
#                 existing_book.category = BOOK_CATEGORIES[book_data['category']]
#                 existing_book.tags = book_data['tags']
#                 existing_book.description = book_data['description']
#                 existing_book.total_copies = book_data['copies']
#                 existing_book.available_copies = book_data['copies']
#                 existing_book.status = 'active'
#
#                 db.session.add(existing_book)
#                 books.append(existing_book)
#             else:
#                 # 创建新图书
#                 book = Book(
#                     isbn=book_data['isbn'],
#                     title=book_data['title'],
#                     author=book_data['author'],
#                     category=BOOK_CATEGORIES[book_data['category']],
#                     tags=book_data['tags'],
#                     description=book_data['description'],
#                     total_copies=book_data['copies'],
#                     available_copies=book_data['copies']
#                 )
#
#                 db.session.add(book)
#                 books.append(book)
#                 print(f"✅ 创建图书: {book.title}")
#
#         db.session.commit()
#         return books
#
#     def generate_random_books(self, count=50):
#         """生成随机图书数据"""
#         print(f"🎲 生成 {count} 本随机图书...")
#         books = []
#
#         categories = list(BOOK_CATEGORIES.values())
#
#         for i in range(count):
#             # 生成唯一ISBN
#             while True:
#                 isbn = self.fake.unique.isbn13()
#                 if not Book.query.filter_by(isbn=isbn).first():
#                     break
#
#             # 修正库存逻辑：available_copies <= total_copies
#             total_copies = random.randint(1, 8)
#             available_copies = random.randint(0, total_copies)  # 确保不会大于total_copies
#
#             book = Book(
#                 isbn=isbn,
#                 title=self.fake.sentence(nb_words=random.randint(2, 5))[:-1],
#                 author=self.fake.name(),
#                 publisher=self.fake.company(),
#                 publish_date=self.fake.date_between(
#                     start_date='-10y',
#                     end_date='today'
#                 ).strftime('%Y-%m'),
#                 category=random.choice(categories),
#                 tags=', '.join(random.sample(POPULAR_TAGS, random.randint(2, 4))),
#                 description=self.fake.paragraph(nb_sentences=2),
#                 total_copies=total_copies,
#                 available_copies=available_copies
#             )
#
#             db.session.add(book)
#             books.append(book)
#
#         db.session.commit()
#         print(f"✅ 成功创建 {len(books)} 本随机图书")
#         return books


import random
from faker import Faker
from app import db
from app.models import Book
from .base_data import BOOK_CATEGORIES, FEATURED_BOOKS

# 图书分类到标签的映射，使用与用户专业相同的键
CATEGORY_TO_TAGS = {
    'computer_science': ['Python', 'Java', '算法', '编程', '机器学习'],
    'software_engineering': ['Python', 'Java', 'Web开发', '数据库', '设计模式'],
    'artificial_intelligence': ['机器学习', '深度学习', '算法', 'Python'],
    'data_science': ['Python', '数据分析', '机器学习', '数据库'],
    'web_development': ['JavaScript', 'HTML', 'CSS', '前端', '后端'],
    'fiction': ['小说', '文学', '散文', '诗歌'],
    'history': ['历史', '传记', '文化', '人物'],
    'economics': ['经济', '管理', '金融', '营销'],
    'science': ['科学', '物理', '化学', '生物']
}

class BookDataGenerator:
    def __init__(self):
        self.fake = Faker('zh_CN')

    def create_featured_books(self):
        # ... 保持不变 ...
        pass

    def generate_random_books(self, count=50):
        print(f"🎲 生成 {count} 本随机图书...")
        books = []
        categories = list(CATEGORY_TO_TAGS.keys())  # 使用相同的键

        for i in range(count):
            while True:
                isbn = self.fake.unique.isbn13()
                if not Book.query.filter_by(isbn=isbn).first():
                    break
            total_copies = random.randint(1, 8)
            available_copies = random.randint(0, total_copies)
            category = random.choice(categories)
            tags_list = CATEGORY_TO_TAGS.get(category, ['阅读', '学习'])
            tags = ', '.join(random.sample(tags_list, min(3, len(tags_list))))

            book = Book(
                isbn=isbn,
                title=self.fake.sentence(nb_words=random.randint(2, 5))[:-1],
                author=self.fake.name(),
                publisher=self.fake.company(),
                publish_date=self.fake.date_between(start_date='-10y', end_date='today').strftime('%Y-%m'),
                category=category,  # 使用英文键
                tags=tags,
                description=self.fake.paragraph(nb_sentences=2),
                total_copies=total_copies,
                available_copies=available_copies
            )
            db.session.add(book)
            books.append(book)

        db.session.commit()
        print(f"✅ 成功创建 {len(books)} 本随机图书")
        return books



