
import json
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime
from app import db, login_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    school_id = db.Column(db.String(20), unique=True, nullable=False)
    major = db.Column(db.String(64))
    interest_tags = db.Column(db.Text)
    credit_score = db.Column(db.Integer, default=100, index=True)
    account_status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 新增字段（用于推荐系统）
    last_login = db.Column(db.DateTime)
    preferred_categories = db.Column(db.Text)  # 保留，用于推荐系统

    role = db.Column(db.String(20), default='user')  # 'user' 或 'admin'

    # 关系
    borrow_records = db.relationship('BorrowRecord', backref='user', lazy='dynamic')
    ratings = db.relationship('Rating', backref='user', lazy='dynamic')
    wishlist_items = db.relationship('Wishlist', backref='user_wishlist', lazy='dynamic',
                                     cascade='all, delete-orphan')
    def set_password(self, password):
        self.password_hash = generate_password_hash(
            password,
            method='pbkdf2:sha256',
            salt_length=8
        )

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'

    def get_credit_level(self):
        """获取用户当前的信誉等级"""
        credit_levels = json.loads(CreditConfig.get_config('credit_levels'))
        for level_name, level_config in credit_levels.items():
            if self.credit_score >= level_config['min']:
                return level_name, level_config
        return 'restricted', credit_levels['restricted']

    def get_borrow_limit(self):
        """根据信誉分获取可借阅数量"""
        _, level_config = self.get_credit_level()
        return level_config['borrow_limit']

    def get_borrow_period(self):
        """根据信誉分获取借阅期限"""
        _, level_config = self.get_credit_level()
        return level_config['borrow_days']

    def can_borrow(self):
        """检查用户是否可以借书"""
        if self.account_status != 'active':
            return False, '账户已被冻结'

        # 检查当前借阅数量
        current_borrows = BorrowRecord.query.filter_by(
            user_id=self.id,
            status='borrowed'
        ).count()

        if current_borrows >= self.get_borrow_limit():
            return False, '借阅数量已达上限'

        return True, '可以借阅'

    def is_in_wishlist(self, book_id):
        """检查图书是否已在心愿单"""
        return Wishlist.query.filter_by(
            user_id=self.id,
            book_id=book_id
        ).first() is not None

    def get_wishlist_books(self):
        """获取用户心愿单中的图书列表 - 修复版本"""
        from sqlalchemy.orm import joinedload

        # 直接查询 Wishlist 并加载关联的 Book 对象
        wishlist_items = Wishlist.query.filter_by(
            user_id=self.id
        ).options(joinedload(Wishlist.book)).all()

        # 确保返回的是 Book 对象列表
        books = []
        for item in wishlist_items:
            if item.book:  # 确保 book 不为 None
                books.append(item.book)

        return books


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # 基础信息
    isbn = db.Column(db.String(13))
    title = db.Column(db.String(200), nullable=False, index=True)
    author = db.Column(db.String(100), nullable=False, index=True)
    publisher = db.Column(db.String(100))
    publish_date = db.Column(db.String(20))

    # 分类信息
    category = db.Column(db.String(50), index=True)
    tags = db.Column(db.Text)  # 简化为只有tags，不保留subcategory

    # 描述信息
    description = db.Column(db.Text)
    cover_image = db.Column(db.String(255))  # 保留但不强制使用

    # 库存管理
    total_copies = db.Column(db.Integer, default=1)
    available_copies = db.Column(db.Integer, default=1)

    # 状态管理
    status = db.Column(db.String(20), default='active')  # active, inactive

    # 统计信息
    borrow_count = db.Column(db.Integer, default=0, index=True)
    average_rating = db.Column(db.Float, default=0.0)

    # 系统字段
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    borrow_records = db.relationship('BorrowRecord', backref='book', lazy='dynamic')
    ratings = db.relationship('Rating', backref='book', lazy='dynamic')

    def can_borrow(self):
        """检查图书是否可以借阅"""
        return self.status == 'active' and self.available_copies > 0

    def borrow(self):
        """借出一本书"""
        if self.can_borrow():
            self.available_copies -= 1
            self.borrow_count += 1
            return True
        return False

    def return_book(self):
        """归还一本书"""
        if self.available_copies < self.total_copies:
            self.available_copies += 1
            return True
        return False

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'cover_image': self.cover_image,
            'category': self.category,
            'available_copies': self.available_copies,
            'average_rating': self.average_rating,
            'borrow_count': self.borrow_count,
            'description': self.description
        }

    @property
    def borrow_rate(self):
        """借阅率 = 借阅次数 / (总册数 * 天数)"""
        if self.total_copies == 0:
            return 0.0
        days_since_creation = (datetime.utcnow() - self.created_at).days
        if days_since_creation <= 0:
            days_since_creation = 1
        return round(self.borrow_count / (self.total_copies * days_since_creation), 3)


class Wishlist(db.Model):
    """用户心愿单"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False, index=True)
    added_date = db.Column(db.DateTime, default=datetime.utcnow)
    notification_sent = db.Column(db.Boolean, default=False)  # 库存恢复时是否已通知

    # 唯一约束：避免重复添加
    __table_args__ = (db.UniqueConstraint('user_id', 'book_id', name='unique_user_book_wishlist'),)

    # 关系
    book = db.relationship('Book', backref='wishlisted_by', lazy='joined')

    def __repr__(self):
        return f'<Wishlist user:{self.user_id} book:{self.book_id}>'


class BorrowRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    borrow_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    due_date = db.Column(db.DateTime, index=True)
    return_date = db.Column(db.DateTime, index=True)
    status = db.Column(db.String(20), default='borrowed', index=True)  # borrowed, returned, overdue
    renew_count = db.Column(db.Integer, default=0)  # 续借次数
    rating = db.Column(db.Integer)  # 评分，1-5星

    @property
    def status_display(self):
        """获取状态显示文本"""
        if self.status == 'borrowed' or self.status == 'overdue':
            if self.due_date and self.due_date < datetime.utcnow():
                return '逾期'
            return '在借中'
        elif self.status == 'returned':
            return '已归还'
        return self.status

    @property
    def can_renew(self):
        """检查是否可以续借"""
        max_renew = int(CreditConfig.get_config('max_renew_count', '2'))
        return (self.status == 'borrowed' and
                self.renew_count < max_renew and
                not self.is_overdue)

    @property
    def is_overdue(self):
        """检查是否逾期"""
        return self.status == 'borrowed' and self.due_date and self.due_date < datetime.utcnow()


class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'book_id', name='unique_user_book_rating'),)


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


class CreditConfig(db.Model):
    """信誉分系统配置"""
    id = db.Column(db.Integer, primary_key=True)
    config_key = db.Column(db.String(50), unique=True, nullable=False)
    config_value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(200))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_config(cls, key, default=None):
        config = cls.query.filter_by(config_key=key).first()
        return config.config_value if config else default

    @classmethod
    def set_config(cls, key, value, description=None):
        config = cls.query.filter_by(config_key=key).first()
        if config:
            config.config_value = value
            config.description = description
        else:
            config = cls(
                config_key=key,
                config_value=value,
                description=description
            )
            db.session.add(config)
        db.session.commit()


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    type = db.Column(db.String(50))  # 通知类型，如 'wishlist_available'
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'))
    content = db.Column(db.String(200))  # 通知内容
    link = db.Column(db.String(200))     # 跳转链接（如图书详情页）
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic', cascade='all, delete-orphan'))
    book = db.relationship('Book')


class Exposure(db.Model):
    """用户曝光记录"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    expose_time = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref=db.backref('exposures', lazy='dynamic'))
    book = db.relationship('Book')


class UserAction(db.Model):
    """用户行为记录（用于短期兴趣建模）"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    action_type = db.Column(db.String(20), nullable=False)  # 'click', 'refresh_negative'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref='actions')
    book = db.relationship('Book')



# 默认信誉分配置
DEFAULT_CREDIT_CONFIGS = {
    'default_credit_score': '100',
    'max_credit_score': '200',
    'min_credit_score': '0',
    'borrow_period_days': '30',
    'renew_period_days': '15',
    'max_renew_count': '2',
    'overdue_penalty_per_day': '1',
    'return_earlier_bonus': '2',
    'rec_borrow_weight': '3.0',          # 借阅权重
    'rec_rating_weight_scale': '1.0',    # 评分直接使用值，不额外加权
    'rec_wishlist_weight': '2.0',         # 心愿单权重
    'rec_popular_borrow_weight': '0.6',   # 热门推荐中借阅次数权重
    'rec_popular_rating_weight': '0.4',   # 热门推荐中评分权重
    'rec_hybrid_threshold': '3',          # 协同过滤启用阈值（借阅次数）
    'credit_levels': json.dumps({
        'excellent': {'min': 150, 'borrow_limit': 10, 'borrow_days': 45},
        'good': {'min': 120, 'borrow_limit': 8, 'borrow_days': 35},
        'normal': {'min': 80, 'borrow_limit': 5, 'borrow_days': 30},
        'poor': {'min': 50, 'borrow_limit': 3, 'borrow_days': 20},
        'restricted': {'min': 0, 'borrow_limit': 0, 'borrow_days': 0}
    })
}

class EvaluationResult(db.Model):
    """推荐算法评估结果缓存"""
    id = db.Column(db.Integer, primary_key=True)
    algorithm_name = db.Column(db.String(50), nullable=False)
    precision = db.Column(db.Float, nullable=False)
    recall = db.Column(db.Float, nullable=False)
    f1 = db.Column(db.Float, nullable=False)
    top_n = db.Column(db.Integer, default=10)
    use_rating = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @classmethod
    def get_latest(cls, top_n=10, use_rating=True):
        """获取指定条件下的最新一次评估结果"""
        return cls.query.filter_by(top_n=top_n, use_rating=use_rating).order_by(cls.created_at.desc()).first()

    @classmethod
    def save_results(cls, results, top_n=10, use_rating=True):
        """保存一组评估结果"""
        cls.query.filter_by(top_n=top_n, use_rating=use_rating).delete()
        for algo_name, metrics in results.items():
            if 'error' in metrics:
                continue
            record = cls(
                algorithm_name=algo_name,
                precision=metrics['precision'],
                recall=metrics['recall'],
                f1=metrics['f1'],
                top_n=top_n,
                use_rating=use_rating
            )
            db.session.add(record)
        db.session.commit()
