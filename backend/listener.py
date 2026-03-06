import json
import logging
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, Response, current_app
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import func, case
from models import db, AuditLog, Role

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Listener / Callback Blueprint
# Provides endpoints for payload check-ins, data reception and operational
# monitoring. All incoming data is logged to the AuditLog table.
# ---------------------------------------------------------------------------

LISTENER_ACTIONS = ('payload_checkin', 'data_exfil')
MAX_BODY_BYTES = 10_000          # max accepted body size on public endpoints
MAX_IDENTIFIER_LEN = 128        # max length for identifier / label path params
MAX_DETAIL_STORE = 2_000        # max chars stored in details column

listener_bp = Blueprint('listener', __name__, url_prefix='/api/l')


# ── helpers ────────────────────────────────────────────────────────────────

def _utcnow():
    return datetime.now(timezone.utc)


def _collect_meta() -> dict:
    """Capture request metadata for forensic context."""
    return {
        "method": request.method,
        "user_agent": request.headers.get("User-Agent", ""),
        "content_type": request.content_type or "",
        "accept_language": request.headers.get("Accept-Language", ""),
        "remote_addr": request.remote_addr,
        "forwarded_for": request.headers.get("X-Forwarded-For", ""),
    }


def _build_details(extra: dict | None = None) -> str:
    """Build a JSON details string from metadata + optional extra fields."""
    payload = _collect_meta()
    if extra:
        payload.update(extra)
    return json.dumps(payload, default=str)[:MAX_DETAIL_STORE]


def _log_callback(action: str, target: str, details: str, ip: str):
    """Persist a listener event to the AuditLog."""
    entry = AuditLog(
        user_id=None,
        action=action,
        target=target[:256],
        details=details,
        ip_address=ip,
    )
    db.session.add(entry)
    db.session.commit()
    logger.info("Listener event: action=%s target=%s ip=%s", action, target, ip)


def _validate_path_param(value: str, name: str):
    """Return an error response if a path parameter is too long."""
    if len(value) > MAX_IDENTIFIER_LEN:
        return jsonify({"status": "error", "message": f"{name} too long"}), 400
    return None


def _listener_base_query():
    """Return the base query filtering on listener actions."""
    return AuditLog.query.filter(AuditLog.action.in_(LISTENER_ACTIONS))


# ── public callback endpoints ─────────────────────────────────────────────

@listener_bp.route('/checkin/<identifier>', methods=['GET', 'POST'])
def checkin(identifier):
    """
    Generic check-in endpoint for payloads.
    Records the request method, headers and any submitted body/form data.
    """
    err = _validate_path_param(identifier, "identifier")
    if err:
        return err

    extra: dict = {}
    if request.is_json:
        body = request.get_data(as_text=True)
        if len(body) > MAX_BODY_BYTES:
            return jsonify({"status": "error", "message": "Body too large"}), 413
        extra["data"] = request.get_json(silent=True)
    elif request.form:
        extra["form"] = request.form.to_dict()

    _log_callback(
        'payload_checkin',
        identifier,
        _build_details(extra),
        request.remote_addr,
    )

    return jsonify({
        "status": "success",
        "ts": _utcnow().isoformat(),
        "id": identifier,
    }), 200


@listener_bp.route('/exfil/<label>', methods=['POST'])
def exfiltrate(label):
    """
    Endpoint to receive small data blobs (e.g., hostname, whoami).
    Body is stored truncated in the audit log.
    """
    err = _validate_path_param(label, "label")
    if err:
        return err

    data = request.get_data(as_text=True)
    if len(data) > MAX_BODY_BYTES:
        return jsonify({"status": "error", "message": "Body too large"}), 413

    _log_callback(
        'data_exfil',
        label,
        _build_details({"content": data[:1000]}),
        request.remote_addr,
    )

    return jsonify({
        "status": "success",
        "ts": _utcnow().isoformat(),
        "label": label,
        "bytes_received": len(data),
    }), 200


# ── authenticated dashboard endpoints ─────────────────────────────────────

@listener_bp.route('/events', methods=['GET'])
@jwt_required()
def listener_events():
    """
    Returns listener events with optional filtering.

    Query params:
      page, per_page          – pagination (default 1 / 50, max 200)
      action                  – filter by action (payload_checkin | data_exfil)
      ip                      – filter by exact IP address
      target                  – filter by target (substring match)
      search                  – free-text search across target + details
      since / until           – ISO-8601 datetime bounds
      sort                    – 'asc' or 'desc' (default: desc)
    """
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)

    query = _listener_base_query()

    # ── optional filters ──
    action = request.args.get('action')
    if action and action in LISTENER_ACTIONS:
        query = query.filter(AuditLog.action == action)

    ip_filter = request.args.get('ip')
    if ip_filter:
        query = query.filter(AuditLog.ip_address == ip_filter)

    target_filter = request.args.get('target')
    if target_filter:
        query = query.filter(AuditLog.target.ilike(f"%{target_filter}%"))

    search = request.args.get('search')
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(AuditLog.target.ilike(like), AuditLog.details.ilike(like))
        )

    since = request.args.get('since')
    if since:
        try:
            query = query.filter(AuditLog.timestamp >= datetime.fromisoformat(since))
        except ValueError:
            pass

    until = request.args.get('until')
    if until:
        try:
            query = query.filter(AuditLog.timestamp <= datetime.fromisoformat(until))
        except ValueError:
            pass

    # ── sorting ──
    sort_dir = request.args.get('sort', 'desc')
    order = AuditLog.timestamp.asc() if sort_dir == 'asc' else AuditLog.timestamp.desc()
    query = query.order_by(order)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

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


@listener_bp.route('/stats', methods=['GET'])
@jwt_required()
def listener_stats():
    """
    Returns aggregated statistics for listener events.

    Response includes total counts, per-action breakdown, unique IPs,
    top targets, and an hourly activity timeline for the last 24 h.
    """
    base = _listener_base_query()

    # overall counts
    total = base.count()
    checkins = base.filter(AuditLog.action == 'payload_checkin').count()
    exfils = base.filter(AuditLog.action == 'data_exfil').count()

    # unique IPs
    unique_ips = (
        db.session.query(func.count(func.distinct(AuditLog.ip_address)))
        .filter(AuditLog.action.in_(LISTENER_ACTIONS))
        .scalar()
    ) or 0

    # top 10 targets by hit count
    top_targets = (
        db.session.query(AuditLog.target, func.count(AuditLog.id).label('hits'))
        .filter(AuditLog.action.in_(LISTENER_ACTIONS))
        .group_by(AuditLog.target)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
        .all()
    )

    # top 10 IPs by hit count
    top_ips = (
        db.session.query(AuditLog.ip_address, func.count(AuditLog.id).label('hits'))
        .filter(AuditLog.action.in_(LISTENER_ACTIONS))
        .group_by(AuditLog.ip_address)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
        .all()
    )

    # last-seen per unique target
    last_seen_rows = (
        db.session.query(AuditLog.target, func.max(AuditLog.timestamp).label('last'))
        .filter(AuditLog.action.in_(LISTENER_ACTIONS))
        .group_by(AuditLog.target)
        .order_by(func.max(AuditLog.timestamp).desc())
        .limit(20)
        .all()
    )

    # 24-hour timeline (hourly buckets)
    cutoff = _utcnow() - timedelta(hours=24)
    recent = (
        base.filter(AuditLog.timestamp >= cutoff)
        .order_by(AuditLog.timestamp.asc())
        .all()
    )
    timeline: dict[str, int] = {}
    for ev in recent:
        bucket = ev.timestamp.strftime("%Y-%m-%dT%H:00:00")
        timeline[bucket] = timeline.get(bucket, 0) + 1

    return jsonify({
        "total": total,
        "checkins": checkins,
        "exfils": exfils,
        "unique_ips": unique_ips,
        "top_targets": [{"target": t, "hits": h} for t, h in top_targets],
        "top_ips": [{"ip": ip, "hits": h} for ip, h in top_ips],
        "last_seen": [
            {"target": t, "last_seen": ls.isoformat()} for t, ls in last_seen_rows
        ],
        "timeline_24h": timeline,
    }), 200


@listener_bp.route('/export', methods=['GET'])
@jwt_required()
def export_events():
    """
    Export listener events as a JSON download.
    Accepts the same filter query params as /events (without pagination).
    Max 5 000 rows.
    """
    query = _listener_base_query()

    action = request.args.get('action')
    if action and action in LISTENER_ACTIONS:
        query = query.filter(AuditLog.action == action)

    ip_filter = request.args.get('ip')
    if ip_filter:
        query = query.filter(AuditLog.ip_address == ip_filter)

    since = request.args.get('since')
    if since:
        try:
            query = query.filter(AuditLog.timestamp >= datetime.fromisoformat(since))
        except ValueError:
            pass

    until = request.args.get('until')
    if until:
        try:
            query = query.filter(AuditLog.timestamp <= datetime.fromisoformat(until))
        except ValueError:
            pass

    rows = query.order_by(AuditLog.timestamp.desc()).limit(5000).all()

    payload = json.dumps(
        [e.to_dict() for e in rows],
        indent=2,
        default=str,
    )
    return Response(
        payload,
        mimetype='application/json',
        headers={"Content-Disposition": "attachment; filename=listener_export.json"},
    )


@listener_bp.route('/cleanup', methods=['POST'])
@jwt_required()
def cleanup_old_events():
    """
    Delete listener events older than a given number of days (default 30).
    Admin only.
    """
    if get_jwt().get('role') != Role.ADMIN:
        return jsonify({"error": "Admin access required"}), 403

    days = request.args.get('days', 30, type=int)
    if days < 1:
        return jsonify({"error": "days must be >= 1"}), 400

    cutoff = _utcnow() - timedelta(days=days)
    try:
        num_deleted = (
            AuditLog.query
            .filter(AuditLog.action.in_(LISTENER_ACTIONS))
            .filter(AuditLog.timestamp < cutoff)
            .delete(synchronize_session=False)
        )
        db.session.commit()
        return jsonify({
            "message": f"Deleted {num_deleted} events older than {days} days",
            "deleted": num_deleted,
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.exception("Cleanup failed")
        return jsonify({"error": "Cleanup failed"}), 500


@listener_bp.route('/clear', methods=['DELETE'])
@jwt_required()
def clear_events():
    """Clears all listener-related events from the audit log. Admin only."""
    if get_jwt().get('role') != Role.ADMIN:
        return jsonify({"error": "Admin access required"}), 403

    try:
        num_deleted = (
            AuditLog.query
            .filter(AuditLog.action.in_(LISTENER_ACTIONS))
            .delete(synchronize_session=False)
        )
        db.session.commit()
        return jsonify({"message": f"Deleted {num_deleted} listener events"}), 200
    except Exception as e:
        db.session.rollback()
        logger.exception("Clear failed")
        return jsonify({"error": "Clear failed"}), 500
