from datetime import datetime
from sqlalchemy import func
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt,
)
from models import db, User, AuditLog, Role

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def _log(user_id, action, target=None, details=None, ip=None):
    entry = AuditLog(user_id=user_id, action=action, target=target,
                     details=details, ip_address=ip)
    db.session.add(entry)
    db.session.commit()


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    user = User.query.filter(func.lower(User.username) == username.lower()).first()
    if not user or not user.check_password(password):
        _log(None, 'login_failed', target=username, ip=request.remote_addr)
        return jsonify({"error": "Invalid credentials"}), 401
    if not user.is_active:
        return jsonify({"error": "Account is disabled"}), 403

    user.last_login = datetime.utcnow()
    db.session.commit()

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role},
    )
    refresh_token = create_refresh_token(identity=str(user.id))

    _log(user.id, 'login', ip=request.remote_addr)
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict(),
    }), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))
    if not user or not user.is_active:
        return jsonify({"error": "User not found or disabled"}), 403
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role},
    )
    return jsonify({"access_token": access_token}), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.to_dict()), 200


@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')

    if not user.check_password(old_password):
        return jsonify({"error": "Current password is incorrect"}), 401
    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400

    user.set_password(new_password)
    user.must_change_password = False
    db.session.commit()

    _log(user.id, 'change_password', ip=request.remote_addr)
    return jsonify({"message": "Password changed successfully", "user": user.to_dict()}), 200
