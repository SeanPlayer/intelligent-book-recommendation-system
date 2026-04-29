# """
# 用户测试数据生成
# 生成具有不同特征的测试用户
# """
#
# import random
# from datetime import datetime
#
# from faker import Faker
# from app import db
# from app.models import User
# from .base_data import TEST_USERS, BOOK_CATEGORIES
#
# class UserDataGenerator:
#     """用户数据生成器"""
#
#     def __init__(self):
#         self.fake = Faker('zh_CN')
#         self.majors = list(BOOK_CATEGORIES.keys())
#
#     def create_test_users(self):
#         """创建预定义的测试用户（智能检查）"""
#         print("📝 创建/更新测试用户...")
#         created_users = []
#
#         for user_data in TEST_USERS:
#             # 按学号检查用户是否存在
#             existing_user = User.query.filter_by(school_id=user_data['school_id']).first()
#
#             if existing_user:
#                 print(f"🔄 更新用户: {existing_user.username} (学号: {existing_user.school_id})")
#                 # 更新用户信息（除了密码）
#                 existing_user.username = user_data['username']
#                 existing_user.email = user_data['email']
#                 existing_user.major = user_data['major']
#                 existing_user.interest_tags = user_data['interest_tags']
#                 existing_user.credit_score = user_data['credit_score']
#                 existing_user.role = user_data.get('role', 'user')
#                 existing_user.account_status = 'active'
#
#                 # 如果需要更新密码
#                 if user_data.get('update_password', False):
#                     existing_user.set_password(user_data['password'])
#
#                 db.session.add(existing_user)
#                 created_users.append(existing_user)
#             else:
#                 # 创建新用户
#                 user = User(
#                     school_id=user_data['school_id'],
#                     username=user_data['username'],
#                     email=user_data['email'],
#                     major=user_data['major'],
#                     interest_tags=user_data['interest_tags'],
#                     credit_score=user_data['credit_score'],
#                     role=user_data.get('role', 'user')
#                 )
#                 user.set_password(user_data['password'])
#
#                 db.session.add(user)
#                 db.session.commit()
#                 created_users.append(user)
#                 print(f"✅ 创建用户: {user.username} (学号: {user.school_id})")
#
#         db.session.commit()
#         return created_users
#
#     def generate_random_users(self, count):
#         """生成随机用户（确保用户名/学号唯一）"""
#         users = []
#         # 预定义常用姓氏和名字
#         last_names = ['张', '李', '王', '刘', '陈', '杨', '赵', '黄', '周', '吴']
#         first_names = ['伟', '芳', '娜', '敏', '静', '强', '磊', '洋', '杰', '娟']
#
#         # 记录已生成的用户名和学号，避免重复
#         used_usernames = set(User.query.with_entities(User.username).all())
#         used_school_ids = set(User.query.with_entities(User.school_id).all())
#
#         # 专业列表
#         majors = ['计算机科学与技术', '软件工程', '电子信息工程', '自动化',
#                   '机械工程', '土木工程', '金融学', '会计学', '汉语言文学', 'history']
#
#         # 兴趣标签
#         interests = ['编程, 算法', '阅读, 历史', '音乐, 电影', '运动, 健身',
#                      '摄影, 旅行', '绘画, 设计', '烹饪, 美食', '游戏, 动漫']
#
#         for i in range(count):
#             # 生成唯一用户名：姓氏 + 随机数字（加长避免重复）
#             while True:
#                 last_name = random.choice(last_names)
#                 # 用户名改为：姓氏拼音首字母 + 4位随机数（原2位太容易重复）
#                 username = f"{last_name.lower()}{random.randint(1000, 9999)}"
#                 if username not in used_usernames:
#                     used_usernames.add(username)
#                     break
#
#             # 生成唯一学号：2021开头 + 6位随机数
#             while True:
#                 school_id = f"2021{random.randint(100000, 999999)}"
#                 if school_id not in used_school_ids:
#                     used_school_ids.add(school_id)
#                     break
#
#             # 随机邮箱
#             email = f"{username}@example.org"
#
#             # 创建用户
#             user = User(
#                 username=username,
#                 email=email,
#                 school_id=school_id,
#                 major=random.choice(majors),
#                 interest_tags=random.choice(interests),
#                 credit_score=random.randint(50, 200),
#                 account_status='active',
#                 created_at=datetime.utcnow(),
#                 role='user'
#             )
#             # 设置密码为 123456
#             user.set_password('123456')
#
#             # 先检查是否真的存在（双重保险）
#             if not User.query.filter_by(username=user.username).first() and \
#                     not User.query.filter_by(school_id=user.school_id).first():
#                 db.session.add(user)
#                 users.append(user)
#                 # print(f"✅ 生成用户: {username} (学号: {school_id})")
#
#         # 批量提交（每50个提交一次，避免内存溢出）
#         batch_size = 50
#         for i in range(0, len(users), batch_size):
#             batch = users[i:i + batch_size]
#             try:
#                 db.session.commit()
#                 print(f"🔄 批量提交 {len(batch)} 个用户")
#             except Exception as e:
#                 db.session.rollback()
#                 print(f"❌ 批量提交失败: {e}")
#                 # 单个提交失败的用户
#                 for user in batch:
#                     try:
#                         db.session.add(user)
#                         db.session.commit()
#                         print(f"✅ 单独提交成功: {user.username}")
#                     except Exception as e2:
#                         db.session.rollback()
#                         print(f"❌ 单独提交失败: {user.username} - {e2}")
#
#         return users


import random
from datetime import datetime
from faker import Faker
from app import db
from app.models import User
from .base_data import TEST_USERS, BOOK_CATEGORIES

# 专业（使用 BOOK_CATEGORIES 的键）
MAJOR_TO_INTERESTS = {
    'computer_science': ['Python', 'Java', '算法', '编程'],
    'software_engineering': ['Python', 'Java', 'Web开发', '数据库'],
    'artificial_intelligence': ['机器学习', '深度学习', '算法'],
    'data_science': ['Python', '数据分析', '机器学习'],
    'web_development': ['JavaScript', 'HTML', 'CSS', '前端'],
    'fiction': ['小说', '文学', '散文'],
    'history': ['历史', '传记', '文化'],
    'economics': ['经济', '管理', '金融'],
    'science': ['科学', '物理', '化学', '生物']
}

class UserDataGenerator:
    def __init__(self):
        self.fake = Faker('zh_CN')
        self.majors = list(MAJOR_TO_INTERESTS.keys())

    def create_test_users(self):
        # ... 保持不变 ...
        pass

    def generate_random_users(self, count):
        users = []
        last_names = ['张', '李', '王', '刘', '陈', '杨', '赵', '黄', '周', '吴']
        used_usernames = set(User.query.with_entities(User.username).all())
        used_school_ids = set(User.query.with_entities(User.school_id).all())

        for i in range(count):
            while True:
                last_name = random.choice(last_names)
                username = f"{last_name.lower()}{random.randint(1000, 9999)}"
                if username not in used_usernames:
                    used_usernames.add(username)
                    break
            while True:
                school_id = f"2021{random.randint(100000, 999999)}"
                if school_id not in used_school_ids:
                    used_school_ids.add(school_id)
                    break
            email = f"{username}@example.org"
            # 修正：major 应为字符串
            major = random.choice(self.majors)
            interests_list = MAJOR_TO_INTERESTS.get(major, ['阅读', '学习'])
            interest_tags = ','.join(random.sample(interests_list, min(2, len(interests_list))))

            user = User(
                username=username,
                email=email,
                school_id=school_id,
                major=major,
                interest_tags=interest_tags,
                credit_score=random.randint(50, 200),
                account_status='active',
                created_at=datetime.utcnow(),
                role='user'
            )
            user.set_password('123456')
            if not User.query.filter_by(username=user.username).first() and \
                    not User.query.filter_by(school_id=user.school_id).first():
                db.session.add(user)
                users.append(user)

        # 批量提交...
        return users


