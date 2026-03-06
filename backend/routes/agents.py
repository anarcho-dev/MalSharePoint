"""
Admin-facing agent management routes.

All endpoints require JWT auth with admin role.
"""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from sqlalchemy import func

from models import db, Role, Agent, AgentTask

logger = logging.getLogger(__name__)
agents_bp = Blueprint('agents_admin', __name__, url_prefix='/api/admin/agents')


def _utcnow():
    return datetime.now(timezone.utc)


def _require_admin():
    if get_jwt().get('role') != Role.ADMIN:
        return jsonify({"error": "Admin access required"}), 403
    return None


# ── List agents ────────────────────────────────────────────────────────────

@agents_bp.route('', methods=['GET'])
@jwt_required()
def list_agents():
    err = _require_admin()
    if err:
        return err

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)

    query = Agent.query

    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)

    search = request.args.get('search')
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(
                Agent.hostname.ilike(like),
                Agent.username.ilike(like),
                Agent.internal_ip.ilike(like),
                Agent.external_ip.ilike(like),
            )
        )

    pagination = query.order_by(Agent.last_seen.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "agents": [a.to_dict() for a in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page,
    }), 200


# ── Agent details ──────────────────────────────────────────────────────────

@agents_bp.route('/<agent_id>', methods=['GET'])
@jwt_required()
def get_agent(agent_id):
    err = _require_admin()
    if err:
        return err

    agent = Agent.query.get(agent_id)
    if not agent:
        return jsonify({"error": "Not found"}), 404

    d = agent.to_dict()
    # Include recent tasks
    recent_tasks = (
        AgentTask.query
        .filter_by(agent_id=agent_id)
        .order_by(AgentTask.created_at.desc())
        .limit(50)
        .all()
    )
    d['recent_tasks'] = [t.to_dict() for t in recent_tasks]
    return jsonify(d), 200


# ── Queue task for agent ───────────────────────────────────────────────────

@agents_bp.route('/<agent_id>/tasks', methods=['POST'])
@jwt_required()
def create_task(agent_id):
    err = _require_admin()
    if err:
        return err

    agent = Agent.query.get(agent_id)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404

    data = request.get_json(silent=True) or {}
    command = str(data.get('command', '')).strip()
    if not command:
        return jsonify({"error": "command required"}), 400

    task = AgentTask(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        command=command[:10_000],
        task_type=str(data.get('task_type', 'shell'))[:32],
        status='queued',
        created_by=get_jwt_identity(),
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


# ── List tasks for agent ──────────────────────────────────────────────────

@agents_bp.route('/<agent_id>/tasks', methods=['GET'])
@jwt_required()
def list_tasks(agent_id):
    err = _require_admin()
    if err:
        return err

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)

    status_filter = request.args.get('status')
    query = AgentTask.query.filter_by(agent_id=agent_id)
    if status_filter:
        query = query.filter_by(status=status_filter)

    pagination = query.order_by(AgentTask.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "tasks": [t.to_dict() for t in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page,
    }), 200


# ── Change agent sleep interval ───────────────────────────────────────────

@agents_bp.route('/<agent_id>/sleep', methods=['POST'])
@jwt_required()
def set_sleep(agent_id):
    err = _require_admin()
    if err:
        return err

    agent = Agent.query.get(agent_id)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404

    data = request.get_json(silent=True) or {}
    interval = data.get('sleep_interval', data.get('sleep'))
    jitter = data.get('jitter')

    if interval is not None:
        agent.sleep_interval = max(1, min(int(interval), 3600))
    if jitter is not None:
        agent.jitter = max(0, min(int(jitter), 100))

    # Queue a sleep-change task so the agent picks it up
    task = AgentTask(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        command=json.dumps({'sleep': agent.sleep_interval, 'jitter': agent.jitter}),
        task_type='sleep',
        status='queued',
        created_by=get_jwt_identity(),
    )
    db.session.add(task)
    db.session.commit()

    return jsonify({"message": "Sleep updated", "sleep": agent.sleep_interval, "jitter": agent.jitter}), 200


# ── Kill agent ─────────────────────────────────────────────────────────────

@agents_bp.route('/<agent_id>/kill', methods=['POST'])
@jwt_required()
def kill_agent(agent_id):
    err = _require_admin()
    if err:
        return err

    agent = Agent.query.get(agent_id)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404

    task = AgentTask(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        command='exit',
        task_type='kill',
        status='queued',
        created_by=get_jwt_identity(),
    )
    db.session.add(task)
    agent.status = 'dead'
    db.session.commit()

    return jsonify({"message": "Kill task queued"}), 200


# ── Delete agent record ───────────────────────────────────────────────────

@agents_bp.route('/<agent_id>', methods=['DELETE'])
@jwt_required()
def delete_agent(agent_id):
    err = _require_admin()
    if err:
        return err

    agent = Agent.query.get(agent_id)
    if not agent:
        return jsonify({"error": "Not found"}), 404

    AgentTask.query.filter_by(agent_id=agent_id).delete()
    db.session.delete(agent)
    db.session.commit()
    return jsonify({"message": "Agent deleted"}), 200


# ── Agent statistics ───────────────────────────────────────────────────────

@agents_bp.route('/stats', methods=['GET'])
@jwt_required()
def agent_stats():
    err = _require_admin()
    if err:
        return err

    total = Agent.query.count()
    active = Agent.query.filter_by(status='active').count()
    dormant = Agent.query.filter_by(status='dormant').count()
    dead = Agent.query.filter_by(status='dead').count()

    total_tasks = AgentTask.query.count()
    queued_tasks = AgentTask.query.filter_by(status='queued').count()
    completed_tasks = AgentTask.query.filter_by(status='completed').count()

    return jsonify({
        "total_agents": total,
        "active": active,
        "dormant": dormant,
        "dead": dead,
        "total_tasks": total_tasks,
        "queued_tasks": queued_tasks,
        "completed_tasks": completed_tasks,
    }), 200


# ── Update agent statuses (dormant / dead detection) ──────────────────────

@agents_bp.route('/refresh-status', methods=['POST'])
@jwt_required()
def refresh_agent_status():
    """Mark agents as dormant/dead based on last_seen vs sleep_interval."""
    err = _require_admin()
    if err:
        return err

    now = _utcnow()
    agents = Agent.query.filter(Agent.status.in_(['active', 'dormant'])).all()
    updated = 0

    for agent in agents:
        interval = agent.sleep_interval or 5
        dormant_threshold = now - timedelta(seconds=interval * 3)
        dead_threshold = now - timedelta(seconds=interval * 10)

        if agent.last_seen and agent.last_seen < dead_threshold:
            if agent.status != 'dead':
                agent.status = 'dead'
                updated += 1
        elif agent.last_seen and agent.last_seen < dormant_threshold:
            if agent.status != 'dormant':
                agent.status = 'dormant'
                updated += 1

    db.session.commit()
    return jsonify({"updated": updated}), 200
