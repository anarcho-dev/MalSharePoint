"""
CLI management commands for MalSharePoint.

Usage:
    python manage.py init-db          # create all database tables
    python manage.py create-admin     # create an admin user interactively
    python manage.py list-users       # print all registered users
"""
import sys
import os
from getpass import getpass

# Ensure the backend directory is on the path when called from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app import create_app
from models import db, User, Role


def init_db():
    app = create_app()
    with app.app_context():
        db.create_all()
        print("Database tables created successfully.")


def create_admin():
    app = create_app()
    with app.app_context():
        username = input("Admin username: ").strip()
        email = input("Admin e-mail: ").strip().lower()
        password = getpass("Admin password (min 8 chars): ").strip()

        if len(password) < 8:
            print("Password too short.")
            sys.exit(1)
        if User.query.filter_by(username=username).first():
            print("Username already taken.")
            sys.exit(1)
        if User.query.filter_by(email=email).first():
            print("E-mail already registered.")
            sys.exit(1)

        user = User(username=username, email=email, role=Role.ADMIN)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"Admin user '{username}' created successfully.")


def list_users():
    app = create_app()
    with app.app_context():
        users = User.query.all()
        if not users:
            print("No users found.")
            return
        print(f"{'ID':<5} {'Username':<20} {'Email':<30} {'Role':<10} {'Active'}")
        print("-" * 75)
        for u in users:
            role_display = u.role.value if hasattr(u.role, "value") else str(u.role)
            print(f"{u.id:<5} {u.username:<20} {u.email:<30} {role_display:<10} {u.is_active}")


COMMANDS = {
    'init-db': init_db,
    'create-admin': create_admin,
    'list-users': list_users,
}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: python manage.py [{' | '.join(COMMANDS)}]")
        sys.exit(1)
    COMMANDS[sys.argv[1]]()
