import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User

app = create_app()


def create_admin_user():
    with app.app_context():
        # 检查是否已存在管理员
        admin = User.query.filter_by(role='admin').first()
        if admin:
            print(f"⚠️  管理员已存在: {admin.username} (学号: {admin.school_id})")
            return

        # 创建管理员账户
        admin = User(
            school_id='admin001',
            username='系统管理员',
            email='admin@intellib.com',
            role='admin'
        )
        admin.set_password('admin123')  # 默认密码，建议首次登录后修改

        db.session.add(admin)
        db.session.commit()
        print(" 管理员账户创建成功！")
        print(f"  账号: admin001")
        print(f"  密码: admin123")


if __name__ == '__main__':
    create_admin_user()