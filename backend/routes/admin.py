from functools import wraps
from sqlalchemy import func
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from models import db, User, File, AuditLog, ServerConfig, Role

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

ALLOWED_CONFIG_KEYS = {'max_upload_size_mb', 'require_approval', 'allow_public_files', 'site_title'}


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        if get_jwt().get('role') != Role.ADMIN:        cd /media/jensbecker/SSD4TB/DEV/Projects/MalSharePoint
        source venv/bin/activate
        python backend/app.py &
        cd frontend && npm run dev
            return jsonify({"error": "Admin access required"}), 403
        return fn(*args, **kwargs)
    return wrapper


# ── Users ──────────────────────────────────────────────────────────────────

@admin_bp.route('/users', methods=['GET'])
@admin_required
def list_users():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    pagination = User.query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "users": [u.to_dict() for u in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page,
    }), 200


@admin_bp.route('/users', methods=['POST'])
@admin_required
def create_user():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', Role.USER)

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if role not in (Role.USER, Role.ADMIN, Role.READONLY):
        return jsonify({"error": "Invalid role"}), 400
    if User.query.filter(func.lower(User.username) == username.lower()).first():
        return jsonify({"error": "Username already taken"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    user = User(username=username, email=email, role=role, must_change_password=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "User created successfully", "user": user.to_dict()}), 201


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    current_id = int(get_jwt_identity())
    user = db.get_or_404(User, user_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    if 'role' in data:
        if data['role'] not in (Role.USER, Role.ADMIN, Role.READONLY):
            return jsonify({"error": "Invalid role"}), 400
        if user_id == current_id and data['role'] != Role.ADMIN:
            return jsonify({"error": "Cannot remove your own admin role"}), 400
        user.role = data['role']

    if 'is_active' in data and isinstance(data['is_active'], bool):
        if user_id == current_id and not data['is_active']:
            return jsonify({"error": "Cannot deactivate your own account"}), 400
        user.is_active = data['is_active']

    db.session.commit()
    return jsonify(user.to_dict()), 200


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    current_id = int(get_jwt_identity())
    if user_id == current_id:
        return jsonify({"error": "Cannot delete your own account"}), 400

    user = db.get_or_404(User, user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted"}), 200


# ── Statistics ─────────────────────────────────────────────────────────────

@admin_bp.route('/stats', methods=['GET'])
@admin_required
def stats():
    total_downloads = db.session.query(db.func.sum(File.download_count)).scalar() or 0
    return jsonify({
        "total_users": User.query.count(),
        "active_users": User.query.filter_by(is_active=True).count(),
        "total_files": File.query.count(),
        "public_files": File.query.filter_by(is_public=True).count(),
        "total_downloads": total_downloads,
        "audit_log_entries": AuditLog.query.count(),
    }), 200


# ── Audit logs ─────────────────────────────────────────────────────────────

@admin_bp.route('/logs', methods=['GET'])
@admin_required
def audit_logs():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    pagination = AuditLog.query.order_by(AuditLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "logs": [log.to_dict() for log in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page,
    }), 200


# ── Server configuration ───────────────────────────────────────────────────

@admin_bp.route('/config', methods=['GET'])
@admin_required
def get_config():
    entries = ServerConfig.query.all()
    return jsonify({e.key: e.value for e in entries}), 200


@admin_bp.route('/config', methods=['POST'])
@admin_required
def update_config():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    updated = {}
    for key, value in data.items():
        if key in ALLOWED_CONFIG_KEYS:
            ServerConfig.set(key, value)
            updated[key] = value

    return jsonify({"message": "Configuration updated", "updated": updated}), 200
