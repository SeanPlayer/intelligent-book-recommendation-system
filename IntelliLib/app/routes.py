from datetime import timedelta, datetime
import json
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User, Book, Wishlist, BorrowRecord, Rating, CreditConfig, Notification, Exposure, UserAction, DEFAULT_CREDIT_CONFIGS
from app.forms import RegistrationForm, LoginForm, BookForm
from functools import wraps
from flask import abort, session

# 主蓝图
from flask import Blueprint

from app.recommendation.hybrid import get_personalized_recommendations
from app.recommendation.popularity import get_hot_books
from app.recommendation.content_based import content_based_recommend
from app.recommendation.collaborative import collaborative_recommend
from app.recommendation.matrix_factorization import svd_recommend


main = Blueprint('main', __name__)

CATEGORY_MAP = {
    'computer_science': '计算机科学',
    'software_engineering': '软件工程',
    'artificial_intelligence': '人工智能',
    'data_science': '数据科学',
    'web_development': 'Web开发',
    'fiction': '文学小说',
    'history': '历史传记',
    'economics': '经济管理',
    'science': '自然科学',
    'other': '其他'
}

def get_classic_books(limit=10):
    """经典好书：按平均评分降序（后续可加入时间条件）"""
    return Book.query.filter_by(status='active').order_by(Book.average_rating.desc()).limit(limit).all()


def get_new_books(limit=10):
    """新书速递：按入库时间降序"""
    return Book.query.filter_by(status='active').order_by(Book.created_at.desc()).limit(limit).all()


def apply_exposure_penalty(user_id, books, decay_hours=24, max_penalty=0.5):
    """
    对图书列表应用曝光降权
    :param user_id: 用户ID
    :param books: Book对象列表
    :param decay_hours: 衰减时间窗口（小时），在此窗口内的曝光才计入惩罚
    :param max_penalty: 最大惩罚系数，最终分数乘以该系数
    :return: 重排序后的图书列表
    """
    from app.models import Exposure
    from datetime import datetime, timedelta

    # 查询用户最近 decay_hours 小时内的曝光记录
    since = datetime.utcnow() - timedelta(hours=decay_hours)
    exposures = Exposure.query.filter(
        Exposure.user_id == user_id,
        Exposure.expose_time >= since
    ).all()

    # 统计每本书的曝光次数
    exposure_count = {}
    for exp in exposures:
        exposure_count[exp.book_id] = exposure_count.get(exp.book_id, 0) + 1

    if not exposure_count:
        return books  # 无曝光记录，直接返回

    # 对每本书计算惩罚后的分数（假设原分数已存储在某个地方，这里我们重新计算）
    # 由于我们这里只有books列表，没有原始分数，所以我们直接基于顺序进行惩罚
    # 简单做法：构建一个字典，将曝光次数映射为惩罚因子
    # 惩罚因子 = max_penalty + (1 - max_penalty) * exp(-曝光次数)  或者线性
    # 这里用线性：score = original_score * (1 - exposure_count * factor) 但factor需确保不为负
    # 因为我们没有原始分数，所以直接对列表进行重排序：曝光过的书往后排

    # 将图书分为两组：未曝光、已曝光，各自保持原序，然后将已曝光组附加到后面
    unexposed = []
    exposed = []
    for book in books:
        if book.id in exposure_count:
            exposed.append(book)
        else:
            unexposed.append(book)
    return unexposed + exposed


@main.route('/')
@main.route('/index')
def index():
    # 获取热门图书（用于热门精选和榜单）
    hot_books_all = get_hot_books(limit=10)          # 取前10本热门，用于轮播/精选
    weekly_hot = hot_books_all[:5]                   # 前5作为本周热门
    classic_books = get_hot_books(limit=5)           # 暂时与热门相同（后续可改为经典算法）
    new_books = Book.query.filter_by(status='active').order_by(Book.created_at.desc()).limit(5).all()

    # 登录用户的个性化推荐（暂用热门推荐）
    recommendations_for_home = []
    if current_user.is_authenticated and not current_user.is_admin():
        recommendations_for_home = get_personalized_recommendations(current_user, 4)
    return render_template('index.html',
                           title='首页',
                           hot_books=hot_books_all,      # 用于轮播
                           weekly_hot=weekly_hot,
                           classic_books=classic_books,
                           new_books=new_books,
                           recommendations=recommendations_for_home)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)  # 禁止访问
        return f(*args, **kwargs)
    return decorated_function


def create_wishlist_notifications(book_id):
    """为所有将该书加入心愿单的用户创建通知"""
    from app.models import Wishlist, Notification
    book = Book.query.get(book_id)
    if not book:
        return
    # 查询所有将该书加入心愿单的用户
    wishlists = Wishlist.query.filter_by(book_id=book_id).all()
    for wl in wishlists:
        # 避免重复生成未读通知（同一本书同一用户）
        existing = Notification.query.filter_by(
            user_id=wl.user_id,
            type='wishlist_available',
            book_id=book_id,
            is_read=False
        ).first()
        if existing:
            continue
        content = f'您心愿单中的图书《{book.title}》现在可以借阅了！'
        link = url_for('main.book_detail', book_id=book.id)
        notif = Notification(
            user_id=wl.user_id,
            type='wishlist_available',
            book_id=book_id,
            content=content,
            link=link
        )
        db.session.add(notif)
    db.session.commit()


@main.route('/top-books/<string:type>')
def top_books(type):
    """完整榜单页面，type 可选 'hot', 'classic', 'new'"""
    page = request.args.get('page', 1, type=int)
    per_page = 20  # 每页显示20本

    if type == 'hot':
        query = Book.query.filter_by(status='active').order_by(Book.borrow_count.desc())
        title = '热门图书排行榜'
    elif type == 'classic':
        query = Book.query.filter_by(status='active').order_by(Book.average_rating.desc())
        title = '经典好书排行榜'
    elif type == 'new':
        query = Book.query.filter_by(status='active').order_by(Book.created_at.desc())
        title = '新书上架榜'
    else:
        abort(404)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    books = pagination.items

    return render_template('books/top_list.html',
                           books=books,
                           type=type,
                           title=title,
                           pagination=pagination,
                           per_page=per_page)


@main.route('/books')
def book_list():
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    search = request.args.get('search', '')

    # 基础查询：显示活跃的图书
    # query = Book.query.filter_by(status='active').filter(Book.available_copies > 0)
    query = Book.query.filter_by(status='active')

    # 分类筛选
    if category:
        query = query.filter_by(category=category)

    # 搜索功能
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                Book.title.like(search_term),
                Book.author.like(search_term),
                Book.tags.like(search_term)
            )
        )

    # 分页
    books = query.paginate(
        page=page,
        per_page=12,  # 每页12本
        error_out=False
    )

    # 获取所有分类用于筛选
    categories = db.session.query(Book.category).filter(
        Book.status == 'active',
        Book.available_copies > 0
    ).distinct().all()

    # 分类筛选侧边栏显示为中文
    categories_display = []
    for cat in categories:
        if cat:
            cat_key = cat[0]  # 取出字符串
            categories_display.append({
                'key': cat_key,
                'name': CATEGORY_MAP.get(cat_key, cat_key)
            })

    return render_template(
        'books/list.html',
        title='图书浏览',
        books=books,
        # categories=[c[0] for c in categories],
        categories=categories_display,
        current_category=category,
        search_query=search,
        CATEGORY_MAP = CATEGORY_MAP
    )


@main.route('/books/<int:book_id>')
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    book.category_display = CATEGORY_MAP.get(book.category, book.category)
    # 记录点击行为（如果用户已登录）
    if current_user.is_authenticated and not current_user.is_admin():
        from app.models import UserAction
        action = UserAction(
            user_id=current_user.id,
            book_id=book_id,
            action_type='click'
        )
        db.session.add(action)
        db.session.commit()  # 注意：频繁点击可能影响性能，可考虑异步或批量
    return render_template('books/detail.html', title=book.title, book=book)


# 借阅相关路由
@main.route('/books/<int:book_id>/borrow', methods=['POST'])
@login_required
def borrow_book(book_id):
    """借阅图书"""
    if current_user.is_admin():
        return jsonify({'success': False, 'message': '管理员不能借阅图书'})

    book = Book.query.get_or_404(book_id)

    # 检查用户是否可以借阅
    can_borrow, message = current_user.can_borrow()
    if not can_borrow:
        return jsonify({'success': False, 'message': message})

    # 检查图书是否可借
    if not book.can_borrow():
        return jsonify({'success': False, 'message': '图书暂无库存'})

    try:
        # 创建借阅记录
        borrow_period = current_user.get_borrow_period()
        due_date = datetime.utcnow() + timedelta(days=borrow_period)

        borrow_record = BorrowRecord(
            user_id=current_user.id,
            book_id=book.id,
            due_date=due_date
        )

        # 更新图书库存
        book.available_copies -= 1

        db.session.add(borrow_record)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'借阅成功！请在 {due_date.strftime("%Y-%m-%d")} 前归还'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'借阅失败: {str(e)}'})


@main.route('/borrows/<int:borrow_id>/return', methods=['POST'])
@login_required
def return_book(borrow_id):
    """归还图书（兼容逾期状态）"""
    borrow_record = BorrowRecord.query.get_or_404(borrow_id)

    # 权限检查
    if borrow_record.user_id != current_user.id and not current_user.is_admin():
        abort(403)

    if borrow_record.status == 'returned':
        return jsonify({'success': False, 'message': '图书已归还'})

    try:
        # 更新借阅记录
        borrow_record.return_date = datetime.utcnow()
        borrow_record.status = 'returned'  # 无论是否逾期，归还后都标记为returned

        book = borrow_record.book
        old_available = book.available_copies
        if book.available_copies < book.total_copies:
            book.available_copies += 1
            if old_available == 0 and book.available_copies > 0:
                create_wishlist_notifications(book.id)
        else:
            return jsonify({'success': False, 'message': '库存数据异常，请联系管理员'})

        # 计算信誉分变化（逾期会自动扣更多分）
        credit_change = calculate_credit_change(borrow_record)
        current_user.credit_score += credit_change

        max_credit = int(CreditConfig.get_config('max_credit_score', '200'))
        min_credit = int(CreditConfig.get_config('min_credit_score', '0'))
        current_user.credit_score = max(min_credit, min(max_credit, current_user.credit_score))

        db.session.commit()

        message = f'归还成功！'
        if credit_change > 0:
            message += f' 信誉分+{credit_change}'
        elif credit_change < 0:
            message += f' 信誉分{credit_change}'

        return jsonify({'success': True, 'message': message})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'归还失败: {str(e)}'})


@main.route('/borrows/<int:borrow_id>/renew', methods=['POST'])
@login_required
def renew_book(borrow_id):
    """续借图书"""
    borrow_record = BorrowRecord.query.get_or_404(borrow_id)

    if borrow_record.user_id != current_user.id:
        abort(403)

    if not borrow_record.can_renew:
        return jsonify({'success': False, 'message': '无法续借'})

    try:
        # 更新续借信息
        renew_days = int(CreditConfig.get_config('renew_period_days', '15'))
        borrow_record.due_date += timedelta(days=renew_days)
        borrow_record.renew_count += 1

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'续借成功！新的归还日期: {borrow_record.due_date.strftime("%Y-%m-%d")}'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'续借失败: {str(e)}'})


@main.route('/my-borrows')
@login_required
def my_borrows():
    """我的借阅记录"""
    borrows = BorrowRecord.query.filter_by(user_id=current_user.id) \
        .order_by(BorrowRecord.borrow_date.desc()) \
        .all()

    return render_template('books/my_borrows.html',
                           title='我的借阅',
                           borrows=borrows)


def calculate_credit_change(borrow_record):
    """计算归还图书时的信誉分变化"""
    if borrow_record.return_date > borrow_record.due_date:
        # 逾期归还，计算扣分
        overdue_days = (borrow_record.return_date - borrow_record.due_date).days
        penalty_per_day = int(CreditConfig.get_config('overdue_penalty_per_day', '1'))
        return -overdue_days * penalty_per_day
    elif borrow_record.return_date < borrow_record.due_date - timedelta(days=3):
        # 提前3天以上归还，奖励
        bonus = int(CreditConfig.get_config('return_earlier_bonus', '2'))
        return bonus
    else:
        # 按时归还，无变化
        return 0


@main.route('/borrows/<int:borrow_id>/rate', methods=['POST'])
@login_required
def rate_book(borrow_id):
    """评分图书"""
    borrow_record = BorrowRecord.query.get_or_404(borrow_id)

    # 权限检查
    if borrow_record.user_id != current_user.id:
        return jsonify({'success': False, 'message': '无权操作'})

    # 只能对已归还的图书评分
    if borrow_record.status != 'returned':
        return jsonify({'success': False, 'message': '只能对已归还的图书评分'})

    data = request.get_json()
    rating_value = data.get('rating')

    if not rating_value or not 1 <= rating_value <= 5:
        return jsonify({'success': False, 'message': '评分必须在1-5之间'})

    try:
        # 检查是否已存在评分
        existing_rating = Rating.query.filter_by(
            user_id=current_user.id,
            book_id=borrow_record.book_id
        ).first()

        if existing_rating:
            # 更新原有评分
            existing_rating.rating = rating_value
        else:
            # 创建新评分
            rating = Rating(
                user_id=current_user.id,
                book_id=borrow_record.book_id,
                rating=rating_value
            )
            db.session.add(rating)

        # 更新借阅记录的评分字段
        borrow_record.rating = rating_value

        # 更新图书平均评分
        book = borrow_record.book
        book_ratings = Rating.query.filter_by(book_id=book.id).all()
        if book_ratings:
            total_rating = sum(r.rating for r in book_ratings)
            book.average_rating = round(total_rating / len(book_ratings), 1)

        db.session.commit()

        return jsonify({'success': True, 'message': '评分成功'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'评分失败: {str(e)}'})








# 认证蓝图
auth = Blueprint('auth', __name__)


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            school_id=form.school_id.data,
            username=form.username.data,
            email=form.email.data,
            major=form.major.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('恭喜，注册成功！', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', title='注册', form=form)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(school_id=form.school_id.data).first()

        # 检查用户是否存在
        if user is None:
            flash('学号/工号或密码无效', 'error')
            return redirect(url_for('auth.login'))

        # 检查密码是否正确
        if not user.check_password(form.password.data):
            flash('学号/工号或密码无效', 'error')
            return redirect(url_for('auth.login'))

        # 检查用户状态 - 新增的检查逻辑
        if user.account_status != 'active':
            flash('您的账户已被冻结，请联系管理员', 'error')
            return redirect(url_for('auth.login'))

        # 所有检查通过，登录用户
        login_user(user)

        # 更新最后登录时间
        user.last_login = datetime.utcnow()
        db.session.commit()

        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('main.index')
        return redirect(next_page)

    return render_template('auth/login.html', title='登录', form=form)


@auth.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))


# 管理员蓝图
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# 管理员登录路由
@auth.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated and current_user.is_admin():
        return redirect(url_for('admin.manage_books'))

    from app.forms import AdminLoginForm   # 导入新表单
    form = AdminLoginForm()
    if form.validate_on_submit():
        # 查询管理员账号（admin_id 对应 User 表的 school_id 字段）
        user = User.query.filter_by(school_id=form.admin_id.data, role='admin').first()

        if not user or not user.check_password(form.password.data):
            flash('管理员账号或密码无效', 'error')
            return redirect(url_for('auth.admin_login'))

        if user.account_status != 'active':
            flash('管理员账户已被冻结', 'error')
            return redirect(url_for('auth.admin_login'))

        login_user(user)
        user.last_login = datetime.utcnow()
        db.session.commit()
        return redirect(url_for('admin.manage_books'))

    return render_template('auth/admin_login.html', title='管理员登录', form=form)


@admin_bp.route('/books')
@login_required
@admin_required
def manage_books():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    stock = request.args.get('stock', '')  # 'available' or 'unavailable' or ''
    # 1. 添加分页参数（默认第1页，每页20条）
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # 基础查询：只显示活跃的图书
    query = Book.query.filter_by(status='active')

    # 搜索功能（按书名、作者、ISBN）
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                Book.title.like(search_term),
                Book.author.like(search_term),
                Book.isbn.like(search_term)
            )
        )

    # 分类筛选
    if category:
        query = query.filter_by(category=category)

    # 库存筛选
    if stock == 'available':
        query = query.filter(Book.available_copies > 0)
    elif stock == 'unavailable':
        query = query.filter(Book.available_copies == 0)

    # 2. 分页查询
    pagination = query.order_by(Book.id.asc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False  # 页码超出范围时返回空列表，不报错
    )

    # 获取所有分类供筛选下拉框使用
    categories = db.session.query(Book.category).filter(Book.status == 'active').distinct().all()
    categories = [c[0] for c in categories if c[0]]

    # 3. 返回pagination对象（
    return render_template('admin/books.html',
                           books=pagination,  # 这里books是分页对象
                           search=search,
                           category=category,
                           stock=stock,
                           categories=categories)


@admin_bp.route('/books/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_book():
    form = BookForm()
    if form.validate_on_submit():
        # 标准化标签
        tags = form.tags.data
        if tags:
            tags = tags.replace('，', ',')
            tags_list = [tag.strip() for tag in tags.split(',')]
            standardized_tags = ','.join(tags_list)
        else:
            standardized_tags = ''

        # 检查是否已存在相同ISBN的活跃图书
        existing_book = None
        if form.isbn.data:
            existing_book = Book.query.filter_by(
                isbn=form.isbn.data,
                status='active'
            ).first()

        if existing_book:
            # 增加库存
            existing_book.total_copies += form.total_copies.data
            old_available = existing_book.available_copies
            existing_book.available_copies += form.total_copies.data
            if old_available == 0 and existing_book.available_copies > 0:
                create_wishlist_notifications(existing_book.id)
            db.session.commit()
            flash(f'已存在相同ISBN的图书"{existing_book.title}"，已增加库存', 'success')
        else:
            # 创建新图书
            book = Book(
                isbn=form.isbn.data,
                title=form.title.data,
                author=form.author.data,
                publisher=form.publisher.data,
                publish_date=form.publish_date.data,
                category=form.category.data,
                subcategory=form.subcategory.data,
                tags=standardized_tags,
                description=form.description.data,
                cover_image=form.cover_image.data,
                total_copies=form.total_copies.data,
                available_copies=form.total_copies.data
            )
            db.session.add(book)
            db.session.commit()
            flash('图书添加成功！', 'success')

        return redirect(url_for('admin.manage_books'))
    return render_template('admin/add_book.html', title='添加图书', form=form)


@admin_bp.route('/books/<int:book_id>/delete')
@login_required
@admin_required
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)

    # 检查是否有未归还的图书
    active_borrows = book.borrow_records.filter_by(status='borrowed').count()

    if active_borrows > 0:
        flash(f'该图书尚有{active_borrows}本未归还，无法删除！', 'error')
    elif book.total_copies > 1:
        # 减少库存而不是删除
        book.total_copies -= 1
        book.available_copies -= 1
        db.session.commit()
        flash('已减少一本图书库存', 'success')
    else:
        # 只有一本且无借阅记录，可以设置为非活跃
        book.status = 'inactive'
        db.session.commit()
        flash('图书已设置为非活跃状态', 'success')

    return redirect(url_for('admin.manage_books'))


@admin_bp.route('/books/<int:book_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)
    form = BookForm(obj=book)

    if form.validate_on_submit():
        # 标准化标签
        tags = form.tags.data
        if tags:
            tags = tags.replace('，', ',')
            tags_list = [tag.strip() for tag in tags.split(',')]
            standardized_tags = ','.join(tags_list)
        else:
            standardized_tags = ''

        # 更新图书信息
        book.isbn = form.isbn.data
        book.title = form.title.data
        book.author = form.author.data
        book.publisher = form.publisher.data
        book.publish_date = form.publish_date.data
        book.category = form.category.data
        book.subcategory = form.subcategory.data
        book.tags = standardized_tags
        book.description = form.description.data
        book.cover_image = form.cover_image.data

        # 特别注意：库存调整逻辑
        old_total = book.total_copies
        new_total = form.total_copies.data

        if new_total > old_total:
            # 增加库存
            diff = new_total - old_total
            old_available = book.available_copies
            book.total_copies = new_total
            book.available_copies += diff
            if old_available == 0 and book.available_copies > 0:
                create_wishlist_notifications(book.id)
        elif new_total < old_total:
            # 减少库存，但要确保不会导致可用库存为负
            diff = old_total - new_total
            if book.available_copies >= diff:
                book.total_copies = new_total
                book.available_copies -= diff
            else:
                flash('减少的库存数量不能超过当前可用库存', 'error')
                return render_template('admin/edit_book.html', title='编辑图书', form=form, book=book)

        db.session.commit()
        flash('图书信息更新成功！', 'success')
        return redirect(url_for('admin.manage_books'))

    return render_template('admin/edit_book.html', title='编辑图书', form=form, book=book)


@admin_bp.route('/credit-config', methods=['GET', 'POST'])
@login_required
@admin_required
def credit_config():
    if request.method == 'POST':
        for key in request.form:
            if key.startswith('config_'):
                config_key = key.replace('config_', '')
                CreditConfig.set_config(config_key, request.form[key])
        flash('信誉分配置已更新！', 'success')
        return redirect(url_for('admin.credit_config'))

    # 获取所有配置
    configs = CreditConfig.query.all()
    config_dict = {config.config_key: config.config_value for config in configs}

    # 确保所有默认配置都存在
    for key, value in DEFAULT_CREDIT_CONFIGS.items():
        if key not in config_dict:
            CreditConfig.set_config(key, value)
            config_dict[key] = value

    return render_template('admin/credit_config.html',
                           title='信誉分配置',
                           configs=config_dict)


@admin_bp.route('/credit-config/reset-defaults')
@login_required
@admin_required
def reset_credit_config():
    """重置为默认配置"""
    for key, value in DEFAULT_CREDIT_CONFIGS.items():
        CreditConfig.set_config(key, value)
    flash('已重置为默认配置！', 'success')
    return redirect(url_for('admin.credit_config'))


@admin_bp.route('/users')
@login_required
@admin_required
def manage_users():
    """用户管理页面"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')

    # 基础查询：只查询普通用户
    query = User.query.filter_by(role='user')

    # 搜索功能
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                User.school_id.like(search_term),
                User.username.like(search_term),
                User.email.like(search_term)
            )
        )

    # 状态筛选
    if status_filter:
        query = query.filter(User.account_status == status_filter)

    # 排序：按id升序
    users = query.order_by(User.id.asc()).paginate(
        page=page,
        per_page=10,
        error_out=False
    )

    return render_template('admin/users.html',
                           users=users,
                           search=search,
                           status_filter=status_filter)


@admin_bp.route('/users/<int:user_id>')
@login_required
@admin_required
def user_detail(user_id):
    """用户详情页面"""
    user = User.query.get_or_404(user_id)

    # 获取用户的借阅记录
    borrows = BorrowRecord.query.filter_by(user_id=user_id) \
        .order_by(BorrowRecord.borrow_date.desc()) \
        .limit(20).all()

    return render_template('admin/user_detail.html',
                           title=f'用户详情 - {user.username}',
                           user=user,
                           borrows=borrows)


@admin_bp.route('/users/<int:user_id>/toggle_status')
@login_required
@admin_required
def toggle_user_status(user_id):
    """冻结/解冻用户"""
    user = User.query.get_or_404(user_id)

    # 不能操作自己
    if user.id == current_user.id:
        flash('不能操作自己的账户', 'error')
        return redirect(url_for('admin.manage_users'))

    # 切换状态
    if user.account_status == 'active':
        user.account_status = 'frozen'
        message = f'已冻结用户 {user.username}'
    else:
        user.account_status = 'active'
        message = f'已解冻用户 {user.username}'

    db.session.commit()
    flash(message, 'success')
    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/users/<int:user_id>/reset_password')
@login_required
@admin_required
def reset_user_password(user_id):
    """重置用户密码"""
    user = User.query.get_or_404(user_id)

    # 使用学号后6位作为默认密码
    default_password = user.school_id[-6:]
    user.set_password(default_password)

    db.session.commit()
    flash(f'已重置用户 {user.username} 的密码为学号后6位', 'success')
    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """管理员仪表盘"""
    # 基础统计数据
    total_books = Book.query.filter_by(status='active').count()
    total_users = User.query.count()
    total_borrows = BorrowRecord.query.count()
    active_borrows = BorrowRecord.query.filter_by(status='borrowed').count()

    # 今日统计
    today = datetime.utcnow().date()
    today_borrows = BorrowRecord.query.filter(
        db.func.date(BorrowRecord.borrow_date) == today
    ).count()
    today_returns = BorrowRecord.query.filter(
        db.func.date(BorrowRecord.return_date) == today
    ).count()

    # 其他统计指标
    total_ratings = Rating.query.count()
    avg_book_rating = db.session.query(db.func.avg(Book.average_rating)).scalar() or 0
    overdue_borrows = BorrowRecord.query.filter(
        BorrowRecord.status == 'borrowed',
        BorrowRecord.due_date < datetime.utcnow()
    ).count()

    # 用户信誉分分布
    credit_distribution = {
        'excellent': User.query.filter(User.credit_score >= 150).count(),
        'good': User.query.filter(User.credit_score >= 120, User.credit_score < 150).count(),
        'normal': User.query.filter(User.credit_score >= 80, User.credit_score < 120).count(),
        'poor': User.query.filter(User.credit_score >= 50, User.credit_score < 80).count(),
        'restricted': User.query.filter(User.credit_score < 50).count()
    }

    # 热门图书（借阅次数最多）
    popular_books = Book.query.filter_by(status='active') \
        .order_by(Book.borrow_count.desc()) \
        .limit(5).all()

    # 热门分类
    from sqlalchemy import func
    popular_categories = db.session.query(
        Book.category,
        func.count(Book.id).label('count')
    ).filter(Book.status == 'active') \
        .group_by(Book.category) \
        .order_by(func.count(Book.id).desc()) \
        .limit(8).all()

    # 最近7天借阅趋势
    last_7_days = []
    borrow_trend = []
    for i in range(6, -1, -1):
        date = datetime.utcnow().date() - timedelta(days=i)
        day_borrows = BorrowRecord.query.filter(
            db.func.date(BorrowRecord.borrow_date) == date
        ).count()
        last_7_days.append(date.strftime('%m-%d'))
        borrow_trend.append(day_borrows)

    return render_template('admin/dashboard.html',
                           title='数据统计',
                           total_books=total_books,
                           total_users=total_users,
                           total_borrows=total_borrows,
                           active_borrows=active_borrows,
                           today_borrows=today_borrows,
                           today_returns=today_returns,
                           total_ratings=total_ratings,
                           avg_book_rating=round(avg_book_rating, 1),
                           overdue_borrows=overdue_borrows,
                           credit_distribution=credit_distribution,
                           popular_books=popular_books,
                           popular_categories=popular_categories,
                           last_7_days=last_7_days,
                           borrow_trend=borrow_trend)


@admin_bp.route('/recommendation-analytics')
@login_required
@admin_required
def recommendation_analytics():
    """推荐系统分析页面"""
    # 基础数据统计
    total_users = User.query.count()
    total_books = Book.query.filter_by(status='active').count()
    total_ratings = Rating.query.count()
    total_borrows = BorrowRecord.query.count()

    # 用户评分分布
    rating_distribution = {
        1: Rating.query.filter_by(rating=1).count(),
        2: Rating.query.filter_by(rating=2).count(),
        3: Rating.query.filter_by(rating=3).count(),
        4: Rating.query.filter_by(rating=4).count(),
        5: Rating.query.filter_by(rating=5).count()
    }

    # 热门分类（用于内容推荐分析）
    from sqlalchemy import func
    category_stats = db.session.query(
        Book.category,
        func.count(Book.id).label('book_count'),
        func.avg(Book.average_rating).label('avg_rating'),
        func.sum(Book.borrow_count).label('total_borrows')
    ).filter(Book.status == 'active') \
        .group_by(Book.category) \
        .all()

    return render_template('admin/recommendation_analytics.html',
                           title='推荐系统分析',
                           total_users=total_users,
                           total_books=total_books,
                           total_ratings=total_ratings,
                           total_borrows=total_borrows,
                           rating_distribution=rating_distribution,
                           category_stats=category_stats)


@admin_bp.route('/run-evaluation')
@login_required
@admin_required
def run_evaluation():
    use_rating = request.args.get('use_rating', '1') == '1'
    top_n = request.args.get('top_n', 10, type=int)
    force = request.args.get('force', '0') == '1'  # 是否强制重新评估

    from app.models import EvaluationResult
    # 检查是否有最近的有效结果（例如1小时内）
    if not force:
        latest = EvaluationResult.get_latest(top_n=top_n, use_rating=use_rating)
        if latest:
            # 如果存在，则直接返回上一次的结果（可附加时间信息）
            results = {}
            all_records = EvaluationResult.query.filter_by(top_n=top_n, use_rating=use_rating).all()
            for r in all_records:
                results[r.algorithm_name] = {
                    'precision': r.precision,
                    'recall': r.recall,
                    'f1': r.f1
                }
            return jsonify({
                'cached': True,
                'timestamp': latest.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'results': results
            })

    # 否则执行新的评估
    from app.recommendation.evaluation import evaluate_all_algorithms
    try:
        results = evaluate_all_algorithms(top_n=top_n, use_rating=use_rating)
        # 存储结果
        EvaluationResult.save_results(results, top_n=top_n, use_rating=use_rating)
        return jsonify({
            'cached': False,
            'results': results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/get-latest-evaluation')
@login_required
@admin_required
def get_latest_evaluation():
    use_rating = request.args.get('use_rating', '1') == '1'
    top_n = request.args.get('top_n', 10, type=int)
    from app.models import EvaluationResult
    latest = EvaluationResult.get_latest(top_n=top_n, use_rating=use_rating)
    if not latest:
        return jsonify({'cached': False, 'results': {}})
    all_records = EvaluationResult.query.filter_by(top_n=top_n, use_rating=use_rating).all()
    results = {}
    for r in all_records:
        results[r.algorithm_name] = {
            'precision': r.precision,
            'recall': r.recall,
            'f1': r.f1
        }
    return jsonify({
        'cached': True,
        'timestamp': latest.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'results': results
    })


@admin_bp.route('/train-fm', methods=['POST'])
@login_required
@admin_required
def train_fm():
    from app.recommendation.fm_recommender import get_fm_recommender
    try:
        get_fm_recommender(force_retrain=True, use_rating=True)
        return jsonify({'success': True, 'message': 'FM模型训练成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# 用户个人中心
@main.route('/user-center')
@login_required
def user_center():
    """用户个人中心 - 修复版本"""
    if current_user.is_admin():
        return redirect(url_for('admin.manage_books'))

    # 获取用户当前借阅
    current_borrows = BorrowRecord.query.filter_by(
        user_id=current_user.id,
        status='borrowed'
    ).order_by(BorrowRecord.due_date.asc()).all()

    # 获取用户最近5条借阅历史
    recent_borrows = BorrowRecord.query.filter_by(
        user_id=current_user.id
    ).order_by(BorrowRecord.borrow_date.desc()).limit(5).all()

    # 获取用户心愿单 - 添加调试信息
    try:
        wishlist_items = current_user.get_wishlist_books()
        print(f"Debug: wishlist_items type: {type(wishlist_items)}")
        print(f"Debug: wishlist_items length: {len(wishlist_items)}")
        if wishlist_items:
            print(f"Debug: first item type: {type(wishlist_items[0])}")
            print(f"Debug: first item: {wishlist_items[0]}")
    except Exception as e:
        print(f"Error getting wishlist: {e}")
        wishlist_items = []

    return render_template(
        'user/center.html',
        title='个人中心',
        current_borrows=current_borrows,
        recent_borrows=recent_borrows,
        wishlist_items=wishlist_items,
        wishlist_count=len(wishlist_items)
    )


@main.route('/wishlist')
@login_required
def my_wishlist():
    """我的心愿单页面"""
    if current_user.is_admin():
        abort(403)

    wishlist_items = current_user.get_wishlist_books()

    return render_template(
        'user/wishlist.html',
        title='我的心愿单',
        wishlist_items=wishlist_items
    )


@main.route('/wishlist/add/<int:book_id>', methods=['POST'])
@login_required
def add_to_wishlist(book_id):
    """添加图书到心愿单"""
    if current_user.is_admin():
        return jsonify({'success': False, 'message': '管理员不能使用心愿单'})

    book = Book.query.get_or_404(book_id)

    # 检查是否已在心愿单
    if current_user.is_in_wishlist(book_id):
        return jsonify({'success': False, 'message': '已在心愿单中'})

    try:
        wishlist_item = Wishlist(
            user_id=current_user.id,
            book_id=book_id
        )
        db.session.add(wishlist_item)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'"{book.title}" 已添加到心愿单'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'添加失败: {str(e)}'})


@main.route('/wishlist/remove/<int:book_id>', methods=['POST'])
@login_required
def remove_from_wishlist(book_id):
    """从心愿单移除图书"""
    if current_user.is_admin():
        return jsonify({'success': False, 'message': '管理员不能使用心愿单'})

    wishlist_item = Wishlist.query.filter_by(
        user_id=current_user.id,
        book_id=book_id
    ).first()

    if not wishlist_item:
        return jsonify({'success': False, 'message': '不在心愿单中'})

    try:
        db.session.delete(wishlist_item)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '已从心愿单移除'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'移除失败: {str(e)}'})




@main.route('/api/notifications/unread-count')
@login_required
def api_notifications_unread_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})


@main.route('/api/notifications')
@login_required
def api_notifications():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    pagination = Notification.query.filter_by(user_id=current_user.id) \
        .order_by(Notification.created_at.desc()) \
        .paginate(page=page, per_page=per_page, error_out=False)
    items = [{
        'id': n.id,
        'content': n.content,
        'link': n.link,
        'is_read': n.is_read,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
    } for n in pagination.items]
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })


@main.route('/api/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def api_notification_read(notif_id):
    notif = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first_or_404()
    notif.is_read = True
    db.session.commit()
    return jsonify({'success': True})


@main.route('/api/notifications/read-all', methods=['POST'])
@login_required
def api_notifications_read_all():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})


@main.route('/api/notifications/<int:notif_id>/delete', methods=['DELETE'])
@login_required
def api_notification_delete(notif_id):
    notif = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first_or_404()
    db.session.delete(notif)
    db.session.commit()
    return jsonify({'success': True})


@main.route('/notifications')
@login_required
def notifications():
    return render_template('notifications/index.html', title='通知中心')



# 相似图书推荐（基于内容）
@main.route('/api/books/<int:book_id>/similar')
def api_similar_books(book_id):
    from app.recommendation.content_based import similar_books
    books = similar_books(book_id, limit=6)
    data = []
    for b in books:
        b.category_display = CATEGORY_MAP.get(b.category, b.category)
        book_dict = b.to_dict()
        book_dict['category_display'] = b.category_display
        data.append(book_dict)
    return jsonify(data)

@main.route('/api/exposure', methods=['POST'])
@login_required
def api_exposure():
    """接收前端上报的曝光记录"""
    data = request.get_json()
    book_ids = data.get('book_ids', [])
    if not book_ids:
        return jsonify({'success': False, 'message': '无数据'})

    from app.models import Exposure
    try:
        for bid in book_ids:
            exp = Exposure(user_id=current_user.id, book_id=bid)
            db.session.add(exp)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})










#---------------推荐系统---------------------
@main.route('/recommendations')
@login_required
def recommendations():
    if current_user.is_admin():
        return redirect(url_for('admin.manage_books'))

    recommended_books = get_personalized_recommendations(current_user, 12)

    return render_template('books/recommendations.html',
                           title='猜你喜欢',
                           recommendations=recommended_books)

@main.route('/api/recommend/personalized')
@login_required
def api_personalized_recommend():
    limit = request.args.get('limit', 10, type=int)
    exclude_ids = request.args.getlist('exclude_ids', type=int)
    books = get_personalized_recommendations(current_user, limit, exclude_ids)
    return jsonify({
        'books': [book.to_dict() for book in books]
    })


@main.route('/api/recommend/personalized/html')
@login_required
def api_personalized_recommend_html():
    limit = request.args.get('limit', 4, type=int)
    exclude_ids = request.args.getlist('exclude_ids', type=int)

    # 从会话获取最近推荐过的ID（最多50个）
    recent_rec_ids = session.get('recent_recommendations', [])

    # 获取更多候选（limit*3 保证有足够候选）
    books = get_personalized_recommendations(current_user, limit * 3, exclude_ids)

    # 分离已推荐和未推荐
    normal = []
    penalized = []
    for book in books:
        if book.id in recent_rec_ids:
            penalized.append(book)
        else:
            normal.append(book)

    final_books = normal[:limit]
    if len(final_books) < limit:
        final_books.extend(penalized[:limit - len(final_books)])

    # 更新会话中的最近推荐ID（合并并去重，保留最近50个）
    new_ids = [b.id for b in final_books]
    updated = list(dict.fromkeys(new_ids + recent_rec_ids))[:50]
    session['recent_recommendations'] = updated
    session.modified = True  # 强制保存session

    if not final_books:
        return ''
    from flask import render_template
    html = ''
    for book in final_books:
        html += render_template('_book_card.html', book=book)
    return html


@main.route('/api/recommend/personalized/page')
@login_required
def api_personalized_recommend_page():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    all_recs = get_personalized_recommendations(current_user, page * per_page)
    start = (page - 1) * per_page
    end = start + per_page
    page_recs = all_recs[start:end]

    # 为每本书添加分类显示名
    books_data = []
    for book in page_recs:
        book_dict = book.to_dict()
        book_dict['category_display'] = CATEGORY_MAP.get(book.category, book.category)
        books_data.append(book_dict)

    return jsonify({
        'books': books_data,
        'page': page,
        'has_more': len(page_recs) == per_page
    })

# 用户行为处理
@main.route('/api/action/refresh-negative', methods=['POST'])
@login_required
def api_refresh_negative():
    data = request.get_json()
    book_ids = data.get('book_ids', [])
    if not book_ids:
        return jsonify({'success': False, 'message': '无数据'})
    from app.models import UserAction
    try:
        for bid in book_ids:
            action = UserAction(
                user_id=current_user.id,
                book_id=bid,
                action_type='refresh_negative'
            )
            db.session.add(action)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

