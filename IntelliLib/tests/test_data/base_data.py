"""
基础数据定义 - 包含系统预定义的分类、标签等
用于保持测试数据的一致性
"""

# 图书分类映射
BOOK_CATEGORIES = {
    'computer_science': '计算机科学',
    'software_engineering': '软件工程',
    'artificial_intelligence': '人工智能',
    'data_science': '数据科学',
    'web_development': 'Web开发',
    'fiction': '文学小说',
    'history': '历史传记',
    'economics': '经济管理',
    'science': '自然科学'
}

# 热门标签库
POPULAR_TAGS = [
    'Python', 'Java', '机器学习', '深度学习', 'Web开发', '数据库',
    '算法', '小说', '文学', '历史', '经济', '科学', '教育', '艺术'
]

# 预定义测试用户 - 有鲜明特征便于测试
TEST_USERS = [
    {
        'school_id': '2021001001',
        'username': 'test1',
        'email': 'test1@university.edu.cn',
        'password': '123456',
        'major': 'computer_science',
        'interest_tags': 'Python,机器学习,Web开发',
        'credit_score': 150
    },
    {
        'school_id': '2021001002',
        'username': 'test2',
        'email': 'test2@university.edu.cn',
        'password': '123456',
        'major': 'software_engineering',
        'interest_tags': 'Java,数据库,算法',
        'credit_score': 120
    },
    {
        'school_id': 'admin001',
        'username': 'admin',
        'email': 'admin@university.edu.cn',
        'password': 'admin123',
        'major': 'computer_science',
        'interest_tags': '管理,系统',
        'credit_score': 200,
        'role': 'admin'
    }
]

# 预定义特征图书 - 便于追踪测试
FEATURED_BOOKS = [
    {
        'isbn': '9787115546081',
        'title': 'Python编程从入门到实践',
        'author': '埃里克·马瑟斯',
        'category': 'computer_science',
        'tags': 'Python,编程,入门',
        'description': 'Python入门经典教材',
        'copies': 5
    },
    {
        'isbn': '9787302514523',
        'title': '机器学习',
        'author': '周志华',
        'category': 'artificial_intelligence',
        'tags': '机器学习,人工智能,算法',
        'description': '机器学习领域经典教材',
        'copies': 3
    },
    {
        'isbn': '9787121376953',
        'title': '深入理解Java虚拟机',
        'author': '周志明',
        'category': 'software_engineering',
        'tags': 'Java,JVM,虚拟机',
        'description': '深入讲解Java虚拟机原理',
        'copies': 4
    }
]

