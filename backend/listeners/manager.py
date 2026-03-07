"""
ListenerManager — singleton that manages threaded listener processes.

Supported listener types:
  http  / https  — werkzeug WSGI-based HTTP(S) listeners (existing)
  ssh            — paramiko SSH server (ssh_listener.py)
  dns            — dnslib UDP DNS server (dns_listener.py)
  tcp            — raw TCP socket server (tcp_listener.py)
  smb            — Named-pipe server (SMB; stub — not yet implemented)
  icmp           — ICMP tunnel (stub — requires root, not yet implemented)

Each listener runs as a threading.Thread.  The manager handles start / stop /
restart lifecycle, port-conflict detection, auto-start on boot, and graceful
shutdown.
"""

import json
import logging
import socket
import ssl
import threading
from datetime import datetime, timezone

from werkzeug.serving import make_server

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc)


class _ListenerThread(threading.Thread):
    """Thin wrapper around a werkzeug WSGI server running in a thread."""

    def __init__(self, server, listener_id: int):
        super().__init__(daemon=True, name=f"listener-{listener_id}")
        self.server = server
        self.listener_id = listener_id

    def run(self):
        logger.info("Listener %s thread started on %s:%s",
                     self.listener_id, self.server.host, self.server.port)
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


class ListenerManager:
    """Singleton managing the lifecycle of all listener threads."""

    def __init__(self, app=None):
        self._threads: dict[int, threading.Thread] = {}
        self._lock = threading.Lock()
        self._app = app

    def init_app(self, app):
        self._app = app
        app.extensions['listener_manager'] = self

    # ── helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _port_available(host: str, port: int) -> bool:
        """Quick check whether *host:port* is free."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((host, port))
            return True
        except OSError:
            return False

    def _build_wsgi_app(self, listener_row):
        """Construct the per-listener WSGI application."""
        # Import here to avoid circular imports at module level
        from listeners.wsgi_app import build_listener_wsgi_app
        return build_listener_wsgi_app(listener_row, self._app)

    # ── public API ─────────────────────────────────────────────────────────

    def start_listener(self, listener_id: int) -> dict:
        """Start a listener by its DB id.  Returns a status dict."""
        from models import db, Listener as LModel

        with self._lock:
            if listener_id in self._threads:
                return {"ok": False, "error": "Listener already running"}

        with self._app.app_context():
            listener = db.session.get(LModel, listener_id)
            if listener is None:
                return {"ok": False, "error": "Listener not found"}

            host = listener.bind_address
            port = listener.bind_port
            ltype = listener.listener_type

            # Prevent binding to the main Flask port
            main_port = self._app.config.get('MAIN_PORT', 5005)
            if port == main_port:
                listener.status = 'error'
                listener.error_message = f"Port {port} is reserved for the main app"
                db.session.commit()
                return {"ok": False, "error": listener.error_message}

            # DNS uses UDP — skip TCP port-availability check for DNS
            if ltype != 'dns' and not self._port_available(host, port):
                listener.status = 'error'
                listener.error_message = f"Port {port} is already in use"
                db.session.commit()
                return {"ok": False, "error": listener.error_message}

            # Dispatch to the correct listener implementation
            try:
                thread = self._start_by_type(listener, ltype)
            except Exception as exc:
                listener.status = 'error'
                listener.error_message = str(exc)
                db.session.commit()
                logger.exception("Failed to start listener %s (type=%s)", listener_id, ltype)
                return {"ok": False, "error": str(exc)}

            with self._lock:
                self._threads[listener_id] = thread

            listener.status = 'running'
            listener.error_message = None
            listener.pid = threading.current_thread().ident
            listener.last_started_at = _utcnow()
            db.session.commit()

            logger.info("Listener %s (%s) started on %s:%s", listener_id, ltype, host, port)
            return {"ok": True, "message": f"Listener started on {host}:{port}"}

    def _start_by_type(self, listener, ltype: str):
        """Instantiate and start the thread for the given protocol type."""
        if ltype in ('http', 'https'):
            return self._start_http_listener(listener)
        if ltype == 'ssh':
            from listeners.ssh_listener import start_ssh_listener
            return start_ssh_listener(listener, self._app)
        if ltype == 'dns':
            from listeners.dns_listener import start_dns_listener
            return start_dns_listener(listener, self._app)
        if ltype == 'tcp':
            from listeners.tcp_listener import start_tcp_listener
            return start_tcp_listener(listener, self._app)
        if ltype == 'smb':
            raise NotImplementedError(
                "SMB (named-pipe) listener requires a Windows host or Samba daemon — "
                "not available in this environment."
            )
        if ltype == 'icmp':
            raise NotImplementedError(
                "ICMP listener requires raw socket access (root / CAP_NET_RAW) — "
                "start this listener on a host with the necessary privileges."
            )
        raise ValueError(f"Unknown listener type: {ltype!r}")

    def _start_http_listener(self, listener):
        """Start a werkzeug-based HTTP/HTTPS listener thread."""
        host = listener.bind_address
        port = listener.bind_port

        wsgi_app = self._build_wsgi_app(listener)
        srv = make_server(host, port, wsgi_app, threaded=True)

        if listener.listener_type == 'https':
            if not listener.tls_cert_path or not listener.tls_key_path:
                raise ValueError("HTTPS requires tls_cert_path and tls_key_path")
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(listener.tls_cert_path, listener.tls_key_path)
            srv.socket = ctx.wrap_socket(srv.socket, server_side=True)

        thread = _ListenerThread(srv, listener.id)
        thread.start()
        return thread

    def stop_listener(self, listener_id: int) -> dict:
        """Stop a running listener."""
        from models import db, Listener as LModel

        with self._lock:
            thread = self._threads.pop(listener_id, None)

        if thread is None:
            # Still update DB status if it says running
            with self._app.app_context():
                listener = db.session.get(LModel, listener_id)
                if listener and listener.status == 'running':
                    listener.status = 'stopped'
                    listener.last_stopped_at = _utcnow()
                    db.session.commit()
            return {"ok": True, "message": "Listener was not running (cleaned up DB)"}

        try:
            thread.shutdown()
            thread.join(timeout=5)
        except Exception:
            logger.exception("Error shutting down listener %s", listener_id)

        with self._app.app_context():
            listener = db.session.get(LModel, listener_id)
            if listener:
                listener.status = 'stopped'
                listener.last_stopped_at = _utcnow()
                listener.pid = None
                db.session.commit()

        logger.info("Listener %s stopped", listener_id)
        return {"ok": True, "message": "Listener stopped"}

    def restart_listener(self, listener_id: int) -> dict:
        """Restart = stop + start."""
        self.stop_listener(listener_id)
        return self.start_listener(listener_id)

    def get_status(self, listener_id: int) -> dict:
        """Return in-memory status for a listener."""
        with self._lock:
            thread = self._threads.get(listener_id)
        if thread is None:
            return {"running": False}
        return {"running": thread.is_alive(), "thread_name": thread.name}

    def get_all_status(self) -> dict[int, dict]:
        """Return status for all tracked listeners."""
        with self._lock:
            ids = list(self._threads.keys())
        return {lid: self.get_status(lid) for lid in ids}

    def auto_start(self):
        """Called at app boot — start all listeners whose DB status is 'running'."""
        from models import Listener as LModel
        with self._app.app_context():
            to_start = LModel.query.filter_by(status='running').all()
            for lsn in to_start:
                logger.info("Auto-starting listener %s (%s)", lsn.id, lsn.name)
                result = self.start_listener(lsn.id)
                if not result.get("ok"):
                    logger.warning("Auto-start failed for %s: %s", lsn.id, result.get("error"))

    def shutdown_all(self):
        """Gracefully stop all running listeners."""
        with self._lock:
            ids = list(self._threads.keys())
        for lid in ids:
            self.stop_listener(lid)
        logger.info("All listeners shut down")
