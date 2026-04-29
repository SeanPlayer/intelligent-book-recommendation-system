"""
山东农业大学图书馆数据集导入脚本
功能：从 sdau_library 数据库采样，导入用户、图书、借阅记录
注意：不生成评分，避免唯一键冲突；图书按 ISBN 去重合并
"""

import os
import sys
import random
import pymysql
from datetime import datetime, timedelta
from collections import defaultdict

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app import create_app, db
from app.models import User, Book, BorrowRecord
from tests.test_data.base_data import TEST_USERS  # 保留测试账号定义

# ==================== 配置参数 ====================
# 采样规模
TARGET_USERS = 5000
TARGET_BOOKS = 5000
MIN_BORROWS_PER_USER = 3      # 每个用户最少借阅次数（用于筛选活跃用户）
MIN_BORROWS_PER_BOOK = 2      # 每本书最少被借次数（用于筛选热门书）

# 源数据库连接
SOURCE_DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '',
    'database': 'sdau_library',
    'charset': 'gbk'
}

# 读者类型映射到兴趣标签的关键词
READER_TYPE_TAGS = {
    '教工': '教学,科研',
    '学生本科': '学习,考试',
    '研究生': '研究,论文',
    '博士生': '博士,研究',
    '博士后': '博士后,研究',
    '本馆': '图书馆,管理'
}

# 学院名称到专业代码的映射
COLLEGE_TO_MAJOR = {
    '经济管理学院': 'economics',
    '信息科学与工程学院': 'computer_science',
    '动物科技学院': 'other',
    '水利土木工程学院': 'civil',
    '资源与环境学院': 'environmental_science',
    '机械与电子工程学院': 'mechanical',
    '林学院': 'forestry',
    '植物保护学院': 'agriculture',
    '食品科学与工程学院': 'food_science',
    '生命科学学院': 'biology',
    '文法学院': 'chinese',
    '外国语学院': 'english',
    '理学院': 'mathematics',
    '化学与材料科学学院': 'chemistry',
    '马克思主义学院': 'philosophy',
    '体育与艺术学院': 'arts',
    '国际交流学院': 'other',
    '继续教育学院': 'other',
    '南管委': 'administration',
    '后勤管理处': 'logistics',
    '网络信息技术中心': 'it_center'
}

# ==================== 工具函数 ====================
def connect_source():
    """连接源数据库"""
    return pymysql.connect(**SOURCE_DB_CONFIG)

def parse_sdau_time(time_str):
    """解析山东农业大学数据集的多种时间格式"""
    if not time_str or time_str == 'NULL':
        return None
    cleaned = time_str.strip()
    # 常见格式：'2014-10-1116:22:15' 需转换为 '2014-10-11 16:22:15'
    if len(cleaned) == 19 and cleaned[10] == '-':
        # 格式：YYYY-MM-DD HH:MM:SS 已存在空格
        try:
            return datetime.strptime(cleaned, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass
    # 处理无分隔符的情况
    if len(cleaned) >= 17 and cleaned[4] == '-' and cleaned[7] == '-':
        # 可能是 '2014-10-1116:22:15' 插入空格
        dt_str = cleaned[:10] + ' ' + cleaned[10:]
        try:
            return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass
    # 纯日期格式
    if len(cleaned) == 10 and cleaned[4] == '-' and cleaned[7] == '-':
        try:
            return datetime.strptime(cleaned, '%Y-%m-%d')
        except ValueError:
            pass
    # 其他格式尝试标准解析
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    print(f"警告: 无法解析时间格式 '{time_str}'，将使用当前时间代替")
    return datetime.utcnow()

# ==================== 数据采样 ====================
def analyze_and_sample(conn):
    print("\n📊 分析源数据并采样...")
    with conn.cursor() as cursor:
        # 1. 找出借阅次数达到阈值的读者
        cursor.execute("""
            SELECT READERID, COUNT(*) as cnt
            FROM jieyue
            GROUP BY READERID
            HAVING cnt >= %s
            ORDER BY cnt DESC
            LIMIT %s
        """, (MIN_BORROWS_PER_USER, TARGET_USERS * 2))
        candidate_readers = [row[0] for row in cursor.fetchall()]
        print(f"候选读者数: {len(candidate_readers)}")

        if len(candidate_readers) < TARGET_USERS:
            # 如果不够，降低阈值（但保持活跃性）
            cursor.execute("""
                SELECT READERID, COUNT(*) as cnt
                FROM jieyue
                GROUP BY READERID
                ORDER BY cnt DESC
                LIMIT %s
            """, (TARGET_USERS * 2))
            candidate_readers = [row[0] for row in cursor.fetchall()]
            print(f"调整后候选读者数: {len(candidate_readers)}")

        selected_readers = random.sample(candidate_readers, min(TARGET_USERS, len(candidate_readers)))
        print(f"最终选择读者数: {len(selected_readers)}")

        # 2. 找出这些读者借阅过的所有财产号
        placeholders = ','.join(['%s'] * len(selected_readers))
        cursor.execute(f"""
            SELECT DISTINCT PROPERTYID
            FROM jieyue
            WHERE READERID IN ({placeholders})
        """, selected_readers)
        candidate_props = [row[0] for row in cursor.fetchall()]
        print(f"候选财产号数: {len(candidate_props)}")

        # 3. 筛选借阅次数达到阈值的财产号
        if len(candidate_props) > TARGET_BOOKS:
            placeholders = ','.join(['%s'] * len(candidate_props))
            cursor.execute(f"""
                SELECT PROPERTYID, COUNT(*) as cnt
                FROM jieyue
                WHERE PROPERTYID IN ({placeholders})
                GROUP BY PROPERTYID
                HAVING cnt >= %s
                ORDER BY cnt DESC
                LIMIT %s
            """, candidate_props + [MIN_BORROWS_PER_BOOK, TARGET_BOOKS])
            selected_props = [row[0] for row in cursor.fetchall()]
        else:
            selected_props = candidate_props
        print(f"最终选择财产号数: {len(selected_props)}")

        return selected_readers, selected_props


# ==================== 导入用户 ====================
def import_users(conn, selected_reader_ids):
    print("\n👤 导入用户...")
    if not selected_reader_ids:
        return {}

    placeholders = ','.join(['%s'] * len(selected_reader_ids))
    with conn.cursor() as cursor:
        cursor.execute(f"""
            SELECT READERID, COLLEGE, READERTYPE, GENDER, GRADE
            FROM duzhe
            WHERE READERID IN ({placeholders})
        """, selected_reader_ids)
        readers = cursor.fetchall()

    existing_school_ids = set(User.query.with_entities(User.school_id).all())
    user_mapping = {}
    users_to_insert = []
    batch_size = 500
    total_created = 0

    for reader in readers:
        reader_id, college, reader_type, gender, grade = reader
        base = reader_id[-10:] if len(reader_id) > 10 else reader_id.zfill(10)
        school_id = f"SD{base}"
        while school_id in existing_school_ids:
            school_id = f"SD{base}{random.randint(10, 99)}"
        username = f"sd_{reader_id[:8]}"
        major = COLLEGE_TO_MAJOR.get(college, 'other') if college != 'NULL' else 'other'
        type_tag = READER_TYPE_TAGS.get(reader_type, '学生')
        college_keyword = college.replace('学院', '').strip() if college != 'NULL' else ''
        interest_tags = f"{type_tag},{college_keyword}" if college_keyword else type_tag

        user_dict = {
            'username': username,
            'email': f"{username}@sdau.local",
            'school_id': school_id,
            'major': major,
            'interest_tags': interest_tags,
            'credit_score': random.randint(80, 150),
            'account_status': 'active',
            'role': 'user',
            'password_hash': User.generate_password_hash('123456')
        }
        users_to_insert.append(user_dict)
        user_mapping[reader_id] = None  # 暂存，插入后需更新映射

        if len(users_to_insert) >= batch_size:
            # 批量插入
            db.session.bulk_insert_mappings(User, users_to_insert)
            db.session.commit()
            # 查询刚插入的用户ID（需要按学号查询，因为username可能重复？但学号唯一）
            for ud in users_to_insert:
                user = User.query.filter_by(school_id=ud['school_id']).first()
                if user:
                    # 找到对应的reader_id
                    for rid in user_mapping:
                        if user_mapping[rid] is None and user.school_id == ud['school_id']:
                            user_mapping[rid] = user.id
                            existing_school_ids.add(ud['school_id'])
                            break
            users_to_insert = []
            total_created += batch_size
            print(f"  已创建 {total_created} 个用户")

    # 处理剩余
    if users_to_insert:
        db.session.bulk_insert_mappings(User, users_to_insert)
        db.session.commit()
        for ud in users_to_insert:
            user = User.query.filter_by(school_id=ud['school_id']).first()
            if user:
                for rid in user_mapping:
                    if user_mapping[rid] is None and user.school_id == ud['school_id']:
                        user_mapping[rid] = user.id
                        existing_school_ids.add(ud['school_id'])
                        break
        total_created += len(users_to_insert)
        print(f"  已创建 {total_created} 个用户")

    print(f"✅ 共创建 {total_created} 个用户")
    return user_mapping


# ==================== 导入图书（合并相同书籍）====================
def import_books(conn, selected_property_ids):
    print("\n📚 导入图书（合并相同书籍）...")
    if not selected_property_ids:
        return {}

    # 由于财产号可能很多，我们分批查询以避免SQL过长
    batch_size = 500
    book_groups = defaultdict(list)
    total_processed = 0

    for i in range(0, len(selected_property_ids), batch_size):
        batch_props = selected_property_ids[i:i + batch_size]
        placeholders = ','.join(['%s'] * len(batch_props))
        with conn.cursor() as cursor:
            cursor.execute(f"""
                SELECT 
                    PROPERTYID,
                    BOOKNAME,
                    WRITER,
                    PUBLISHER,
                    ISBN,
                    FIRSTCLASS,
                    SECONDCLASS
                FROM jieyue
                WHERE PROPERTYID IN ({placeholders})
                GROUP BY PROPERTYID
            """, batch_props)
            books_raw = cursor.fetchall()

        for (prop, title, author, publisher, isbn, fc, sc) in books_raw:
            key = isbn.strip() if isbn and isbn != 'NULL' else f"{title}|{author}"
            book_groups[key].append((prop, title, author, publisher, isbn, fc, sc))
        total_processed += len(books_raw)
        print(f"  已处理 {total_processed} 个财产号...")

    print(f"总共形成 {len(book_groups)} 个图书组（按ISBN/书名+作者）")

    # 记录已存在的 ISBN 或 书名+作者 组合
    existing_keys = set()
    existing_books = Book.query.all()
    for b in existing_books:
        if b.isbn and b.isbn.strip():
            existing_keys.add(b.isbn.strip())
        else:
            existing_keys.add(f"{b.title}|{b.author}")

    book_mapping = {}
    created = 0
    updated = 0

    # 分类映射
    category_map = {
        'A': '马列主义', 'B': '哲学宗教', 'C': '社会科学总论',
        'D': '政治法律', 'E': '军事', 'F': '经济',
        'G': '文化教育', 'H': '语言', 'I': '文学',
        'J': '艺术', 'K': '历史地理', 'N': '自然科学总论',
        'O': '数理化', 'P': '天文地球', 'Q': '生物',
        'R': '医药卫生', 'S': '农业', 'T': '工业技术',
        'U': '交通运输', 'V': '航空航天', 'X': '环境安全',
        'Z': '综合'
    }

    for key, items in book_groups.items():
        first = items[0]
        prop, title, author, publisher, isbn, fc, sc = first
        total = len(items)

        # 检查是否已存在
        if key in existing_keys:
            if isbn and isbn.strip():
                book = Book.query.filter_by(isbn=isbn).first()
            else:
                book = Book.query.filter_by(title=title, author=author).first()
            if book:
                book.total_copies += total
                book.available_copies += total
                db.session.add(book)
                db.session.flush()
                updated += 1
                for (p, _, _, _, _, _, _) in items:
                    book_mapping[p] = book.id
                continue

        # 创建新书
        category = category_map.get(fc, '其他')
        tags = f"{fc},{sc},{category}"

        book = Book(
            isbn=isbn if isbn != 'NULL' else '',
            title=title[:200] if title else '未知书名',
            author=author[:100] if author else '未知',
            publisher=publisher[:100] if publisher else '未知',
            publish_date='',
            category=category,
            tags=tags,
            description='',
            cover_image='',
            total_copies=total,
            available_copies=total,
            status='active'
        )
        db.session.add(book)
        db.session.flush()
        created += 1

        for (p, _, _, _, _, _, _) in items:
            book_mapping[p] = book.id

        if (created + updated) % 200 == 0:
            db.session.commit()
            print(f"  已处理 {created + updated} 组图书 (新建{created}, 更新{updated})")

    db.session.commit()
    print(f"✅ 图书处理完成：新建 {created} 种，更新 {updated} 种")
    return book_mapping


# ==================== 导入借阅记录 ====================
def import_borrows(conn, user_mapping, book_mapping, selected_readers, selected_props):
    print("\n📖 导入借阅记录...")
    if not selected_readers or not selected_props:
        return

    batch_size = 100
    total_borrows = 0

    for i in range(0, len(selected_readers), batch_size):
        batch_readers = selected_readers[i:i+batch_size]
        placeholders_reader = ','.join(['%s'] * len(batch_readers))
        # 财产号也分批，避免SQL过长
        for j in range(0, len(selected_props), batch_size):
            batch_props = selected_props[j:j+batch_size]
            placeholders_prop = ','.join(['%s'] * len(batch_props))
            with conn.cursor() as cursor:
                cursor.execute(f"""
                    SELECT 
                        READERID,
                        PROPERTYID,
                        LENDDATE,
                        RETURNDATE,
                        HOLDTIME
                    FROM jieyue
                    WHERE READERID IN ({placeholders_reader})
                      AND PROPERTYID IN ({placeholders_prop})
                """, batch_readers + batch_props)
                records = cursor.fetchall()

            for (reader_id, prop_id, lend_str, return_str, holdtime) in records:
                sys_uid = user_mapping.get(reader_id)
                sys_bid = book_mapping.get(prop_id)
                if not sys_uid or not sys_bid:
                    continue

                borrow_date = parse_sdau_time(lend_str)
                if not borrow_date:
                    continue

                return_date = parse_sdau_time(return_str) if return_str and return_str != 'NULL' else None

                if return_date:
                    due_date = return_date
                    status = 'returned'
                else:
                    due_date = borrow_date + timedelta(days=30)
                    status = 'borrowed' if datetime.utcnow() < due_date else 'overdue'

                borrow = BorrowRecord(
                    user_id=sys_uid,
                    book_id=sys_bid,
                    borrow_date=borrow_date,
                    due_date=due_date,
                    return_date=return_date,
                    status=status,
                    renew_count=0,
                    rating=None
                )
                db.session.add(borrow)
                total_borrows += 1

                if total_borrows % 1000 == 0:
                    db.session.commit()
                    print(f"  已导入 {total_borrows} 条借阅记录")

    db.session.commit()
    print(f"✅ 共导入 {total_borrows} 条借阅记录")


# ==================== 更新图书统计 ====================
def update_book_stats():
    """更新图书的 borrow_count 和 average_rating"""
    print("\n📊 更新图书统计信息...")
    books = Book.query.all()
    for book in books:
        # 借阅次数
        book.borrow_count = BorrowRecord.query.filter_by(book_id=book.id).count()
        # 平均评分（暂不计算，因为没有评分）
        # 如果有评分再计算
    db.session.commit()
    print("✅ 统计信息更新完成")


# ==================== 验证导入结果 ====================
def verify_import():
    """验证导入结果并打印统计"""
    print("\n🔍 验证导入结果...")
    from app.models import User, Book, BorrowRecord
    user_cnt = User.query.filter_by(role='user').count()
    book_cnt = Book.query.filter_by(status='active').count()
    borrow_cnt = BorrowRecord.query.count()
    print(f"最终数据统计:")
    print(f"  普通用户数: {user_cnt}")
    print(f"  活跃图书数: {book_cnt}")
    print(f"  借阅记录数: {borrow_cnt}")
    return user_cnt, book_cnt, borrow_cnt


# ==================== 主函数 ====================
def main():
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("🚀 开始导入山东农业大学图书馆数据集（修正版）")
        print("=" * 60)

        # 1. 连接源数据库
        conn = connect_source()
        # 2. 采样用户和图书
        selected_readers, selected_props = analyze_and_sample(conn)
        # 3. 导入用户
        user_mapping = import_users(conn, selected_readers)
        # 4. 导入图书（合并相同书籍）
        book_mapping = import_books(conn, selected_props)
        # 5. 导入借阅记录（不生成评分）
        import_borrows(conn, user_mapping, book_mapping, selected_readers, selected_props)
        # 6. 更新图书统计
        update_book_stats()
        # 7. 验证
        verify_import()

        conn.close()
        print("\n" + "=" * 60)
        print("✅ 数据导入完成！")
        print("=" * 60)

if __name__ == '__main__':
    # 设置随机种子，保证结果可复现
    random.seed(42)
    main()