from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.models import User

class RegistrationForm(FlaskForm):
    school_id = StringField('学号/工号', validators=[DataRequired(), Length(min=6, max=20)])
    username = StringField('用户名', validators=[DataRequired(), Length(min=2, max=64)])
    email = StringField('邮箱', validators=[DataRequired(), Email()])
    major = SelectField('专业', validators=[DataRequired()], choices=[
        ('', '请选择专业'),
        ('computer_science', '计算机科学'),
        ('software_engineering', '软件工程'),
        ('artificial_intelligence', '人工智能'),
        ('data_science', '数据科学'),
        ('information_security', '信息安全'),
        ('electronics', '电子工程'),
        ('mechanical', '机械工程'),
        ('civil', '土木工程'),
        ('architecture', '建筑学'),
        ('business', '工商管理'),
        ('economics', '经济学'),
        ('finance', '金融学'),
        ('law', '法学'),
        ('medicine', '临床医学'),
        ('pharmacy', '药学'),
        ('mathematics', '数学'),
        ('physics', '物理学'),
        ('chemistry', '化学'),
        ('chinese', '中国语言文学'),
        ('english', '英语'),
        ('history', '历史学'),
        ('other', '其他专业')
    ])
    other_major = StringField('请输入您的专业名称', validators=[Length(max=50)])
    password = PasswordField('密码', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('确认密码', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('注册')

    def validate_school_id(self, school_id):
        user = User.query.filter_by(school_id=school_id.data).first()
        if user:
            raise ValidationError('该学号/工号已被注册。')
        if not school_id.data.isdigit():
            raise ValidationError('学号/工号只能包含数字。')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('该用户名已被使用。')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('该邮箱已被注册。')


class LoginForm(FlaskForm):
    school_id = StringField('学号/工号', validators=[DataRequired()])
    password = PasswordField('密码', validators=[DataRequired()])
    submit = SubmitField('登录')


class AdminLoginForm(FlaskForm):
    admin_id = StringField('管理员账号', validators=[DataRequired()])
    password = PasswordField('密码', validators=[DataRequired()])
    submit = SubmitField('登录')

class BookForm(FlaskForm):
    isbn = StringField('ISBN', validators=[Length(max=13)])
    title = StringField('书名', validators=[DataRequired(), Length(max=200)])
    author = StringField('作者', validators=[DataRequired(), Length(max=100)])
    publisher = StringField('出版社', validators=[Length(max=100)])
    publish_date = StringField('出版日期', validators=[Length(max=20)])  # 简化处理，用字符串
    category = StringField('分类', validators=[DataRequired(), Length(max=50)])
    subcategory = StringField('子分类', validators=[Length(max=50)])
    tags = StringField('标签', validators=[Length(max=300)])  # 用逗号分隔的标签
    description = TextAreaField('描述')
    cover_image = StringField('封面图片URL', validators=[Length(max=255)])
    total_copies = IntegerField('总册数', validators=[DataRequired()], default=1)
    submit = SubmitField('添加图书')


