"""
将原始数据集导入 sdau_library 数据库
"""
import pymysql
import os
import chardet  # 需要安装：pip install chardet

# ====================== 请修改这里的数据库连接信息 ======================
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '',  # 替换成你的密码
    'db': 'sdau_library',
    'charset': 'gbk'
}

# ====================== 数据集文件路径 ======================
DUZHE_SQL_PATH = r"D:\Drivers\传入文件\毕业设计相关信息\资料使用\山东农业大学图书馆数据集\DUZHE.sql"
JIEYUE_SQL_PATH = r"D:\Drivers\传入文件\毕业设计相关信息\资料使用\山东农业大学图书馆数据集\JIEYUE.sql"


def detect_file_encoding(file_path):
    """自动检测文件编码"""
    with open(file_path, 'rb') as f:
        raw_data = f.read(100000)  # 读取前100KB检测编码
        result = chardet.detect(raw_data)
        encoding = result['encoding']
        confidence = result['confidence']
        print(f"📝 文件 {os.path.basename(file_path)} 检测编码: {encoding} (置信度: {confidence:.2f})")
        return encoding if confidence > 0.7 else 'gbk'  # 置信度低则默认gbk


def connect_db():
    """连接数据库"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print("✅ 数据库连接成功")
        return conn, cursor
    except Exception as e:
        print(f"❌ 数据库连接失败：{e}")
        exit(1)


def create_tables(conn, cursor):
    """创建表结构（保持之前的修复版）"""
    create_duzhe_sql = """
    CREATE TABLE IF NOT EXISTS `duzhe` (
        `SEID` INT NOT NULL COMMENT '数据清洗序号',
        `COLLEGE` VARCHAR(200) DEFAULT NULL COMMENT '所属学院',
        `READERTYPE` VARCHAR(20) NOT NULL COMMENT '读者类型',
        `GENDER` VARCHAR(2) DEFAULT NULL COMMENT '性别',
        `READERID` VARCHAR(50) NOT NULL COMMENT '脱敏读者ID',
        `GRADE` VARCHAR(20) DEFAULT NULL COMMENT '入学年级',
        `TOTALLEND` INT NOT NULL COMMENT '累计借阅量',
        PRIMARY KEY (`SEID`),
        INDEX idx_readerid (`READERID`)
    ) ENGINE=InnoDB DEFAULT CHARSET=gbk COMMENT='读者信息表';
    """

    create_jieyue_sql = """
    -- 创建匹配INSERT值数量的jieyue表（18个字段，顺序完全对应）
    CREATE TABLE IF NOT EXISTS `jieyue` (
        `SEID` INT NOT NULL COMMENT '数据清洗序号',  -- 第1个值
        `PROPERTYID` VARCHAR(50) NOT NULL COMMENT '图书财产号',  -- 第2个值
        `LENDDATE` VARCHAR(100) NOT NULL COMMENT '借阅精确时间',  -- 第3个值
        `RETURNDATE` VARCHAR(100) NOT NULL COMMENT '归还/应还时间',  -- 第4个值
        `BOOKLOCATION` VARCHAR(200) NOT NULL COMMENT '馆藏地',  -- 第5个值
        `UNKNOWN_FIELD` VARCHAR(50) DEFAULT NULL COMMENT '未知字段（数据里第6个值）',  -- 第6个值（NULL/D201/B204等）
        `BOOKNAME` VARCHAR(1000) DEFAULT NULL COMMENT '书名',  -- 第7个值
        `WRITER` VARCHAR(1000) DEFAULT NULL COMMENT '著者',  -- 第8个值
        `PUBLISHER` VARCHAR(500) DEFAULT NULL COMMENT '出版社',  -- 第9个值
        `ISBN` VARCHAR(200) DEFAULT NULL COMMENT 'ISBN号',  -- 第10个值
        `SEARCHNUMBER` VARCHAR(200) DEFAULT NULL COMMENT '索书号',  -- 第11个值
        `HOLDTIME` FLOAT NOT NULL COMMENT '持有时长（小时）',  -- 第12个值
        `FIRSTCLASS` VARCHAR(20) NOT NULL COMMENT '一级分类号',  -- 第13个值
        `SECONDCLASS` VARCHAR(50) NOT NULL COMMENT '二级分类号',  -- 第14个值
        `LENDYEAR` INT NOT NULL COMMENT '借阅年份',  -- 第15个值
        `LENDMONTH` INT NOT NULL COMMENT '借阅月份',  -- 第16个值
        `READERID` VARCHAR(50) NOT NULL COMMENT '脱敏读者ID',  -- 第17个值
        `TOTALLEND` INT NOT NULL COMMENT '累计借阅量',  -- 第18个值
        PRIMARY KEY (`SEID`),
        INDEX idx_readerid (`READERID`),
        INDEX idx_lendyear (`LENDYEAR`)
    ) ENGINE=InnoDB DEFAULT CHARSET=gbk COMMENT='借阅记录表';
    """

    try:
        cursor.execute(create_duzhe_sql)
        cursor.execute(create_jieyue_sql)
        conn.commit()
        print("✅ duzhe和jieyue表创建成功")
    except Exception as e:
        conn.rollback()
        print(f"❌ 建表失败：{e}")
        exit(1)


def import_sql_file(conn, cursor, sql_file_path, table_name):
    """逐行读取并导入SQL文件（核心修复）"""
    print(f"\n📥 开始导入 {table_name} 表数据...")

    # 1. 自动检测文件编码
    encoding = detect_file_encoding(sql_file_path)

    success_count = 0
    fail_count = 0
    current_sql = ""
    in_insert = False

    try:
        with open(sql_file_path, 'r', encoding=encoding, errors='replace') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # 跳过注释和空行
                if not line or line.startswith('--') or line.startswith('/*') or line.startswith(
                        'LOCK') or line.startswith('UNLOCK') or line.startswith('/*!'):
                    continue

                # 识别INSERT语句开始
                if line.upper().startswith('INSERT INTO'):
                    in_insert = True
                    current_sql = line
                elif in_insert:
                    # 累积INSERT语句
                    current_sql += " " + line
                    # 识别INSERT语句结束（以;结尾）
                    if line.endswith(';'):
                        # 执行单条INSERT
                        try:
                            cursor.execute(current_sql)
                            conn.commit()
                            success_count += 1
                            # 每1000条打印一次进度
                            if success_count % 1000 == 0:
                                print(f"📊 已导入 {success_count} 条记录（失败：{fail_count}）")
                        except Exception as e:
                            conn.rollback()
                            fail_count += 1
                            # 只打印前10个错误，避免刷屏
                            if fail_count <= 10:
                                print(f"⚠️ 第{line_num}行导入失败（已跳过）: {str(e)[:100]}")
                        # 重置状态
                        in_insert = False
                        current_sql = ""

        print(f"✅ {table_name} 导入完成：成功 {success_count} 条，失败 {fail_count} 条")

    except Exception as e:
        print(f"❌ 读取文件失败：{e}")


def main():
    print("=" * 60)
    print("🚀 开始导入山东农业大学图书馆数据集（修复版）")
    print("=" * 60)

    # 1. 连接数据库
    conn, cursor = connect_db()

    # 2. 创建表结构
    create_tables(conn, cursor)

    # 3. 导入duzhe数据
    import_sql_file(conn, cursor, DUZHE_SQL_PATH, "duzhe")

    # 4. 导入jieyue数据
    import_sql_file(conn, cursor, JIEYUE_SQL_PATH, "jieyue")

    # 5. 关闭连接
    cursor.close()
    conn.close()

    print("\n" + "=" * 60)
    print("✅ 数据集导入完成！")
    print("=" * 60)


if __name__ == '__main__':
    main()