"""
ListenerManager — singleton that manages threaded HTTP/HTTPS listener processes.

Each listener runs as a threading.Thread hosting a lightweight WSGI app via
werkzeug.serving.make_server.  The manager handles start / stop / restart
lifecycle, port-conflict detection, auto-start on boot, and graceful shutdown.
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
        logger.info(
            "Listener %s thread started on %s:%s",
            self.listener_id,
            self.server.host,
            self.server.port,
        )
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


class ListenerManager:
    """Singleton managing the lifecycle of all listener threads."""

    def __init__(self, app=None):
        self._threads: dict[int, _ListenerThread] = {}
        self._lock = threading.Lock()
        self._app = app

    def init_app(self, app):
        self._app = app
        app.extensions["listener_manager"] = self

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

    def _start_http_listener(self, listener):
        """Standard HTTP/HTTPS werkzeug server."""
        host = listener.bind_address
        port = listener.bind_port

        # Build WSGI app
        wsgi_app = self._build_wsgi_app(listener)

        srv = make_server(host, port, wsgi_app, threaded=True)

        # TLS
        if listener.listener_type == "https":
            # Try to get paths from options first (new system), then fall back to DB columns
            import json

            options = json.loads(listener.options) if listener.options else {}
            cert = options.get("tls_cert_path") or listener.tls_cert_path
            key = options.get("tls_key_path") or listener.tls_key_path

            if not cert or not key:
                raise ValueError("HTTPS requires tls_cert_path and tls_key_path")

            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(cert, key)
            srv.socket = ctx.wrap_socket(srv.socket, server_side=True)

        return _ListenerThread(srv, listener.id)

    def _start_ssh_listener(self, listener):
        """Conceptual SSH Listener."""

        # In a real implementation, we would use paramiko or similar
        # For now, we simulate the thread
        class SSHServerThread(threading.Thread):
            def __init__(self, l_id, h, p):
                super().__init__(daemon=True, name=f"ssh-listener-{l_id}")
                self.l_id = l_id
                self.h = h
                self.p = p
                self.active = True

            def run(self):
                logger.info(
                    "SSH Listener %s started on %s:%s (Simulation)",
                    self.l_id,
                    self.h,
                    self.p,
                )
                while self.active:
                    threading.Event().wait(1.0)

            def shutdown(self):
                self.active = False

        return SSHServerThread(listener.id, listener.bind_address, listener.bind_port)

    def _start_dns_listener(self, listener):
        """Conceptual DNS Listener."""

        class DNSServerThread(threading.Thread):
            def __init__(self, l_id, h, p):
                super().__init__(daemon=True, name=f"dns-listener-{l_id}")
                self.l_id = l_id
                self.h = h
                self.p = p
                self.active = True

            def run(self):
                logger.info(
                    "DNS Listener %s started on %s:%s (Simulation)",
                    self.l_id,
                    self.h,
                    self.p,
                )
                while self.active:
                    threading.Event().wait(1.0)

            def shutdown(self):
                self.active = False

        return DNSServerThread(listener.id, listener.bind_address, listener.bind_port)

    def _start_smb_listener(self, listener):
        """Conceptual SMB Listener."""

        class SMBServerThread(threading.Thread):
            def __init__(self, l_id, h, p):
                super().__init__(daemon=True, name=f"smb-listener-{l_id}")
                self.l_id = l_id
                self.h = h
                self.p = p
                self.active = True

            def run(self):
                logger.info(
                    "SMB Listener %s started on %s:%s (Simulation)",
                    self.l_id,
                    self.h,
                    self.p,
                )
                while self.active:
                    threading.Event().wait(1.0)

            def shutdown(self):
                self.active = False

        return SMBServerThread(listener.id, listener.bind_address, listener.bind_port)

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

            # Prevent binding to the main Flask port
            main_port = self._app.config.get("MAIN_PORT", 5005)
            if port == main_port:
                listener.status = "error"
                listener.error_message = f"Port {port} is reserved for the main app"
                db.session.commit()
                return {"ok": False, "error": listener.error_message}

            # Check port availability
            if not self._port_available(host, port):
                listener.status = "error"
                listener.error_message = f"Port {port} is already in use"
                db.session.commit()
                return {"ok": False, "error": listener.error_message}

            # Start the appropriate server based on type
            try:
                if listener.listener_type in ("http", "https"):
                    thread = self._start_http_listener(listener)
                elif listener.listener_type == "ssh":
                    thread = self._start_ssh_listener(listener)
                elif listener.listener_type == "dns":
                    thread = self._start_dns_listener(listener)
                elif listener.listener_type == "smb":
                    thread = self._start_smb_listener(listener)
                else:
                    raise ValueError(
                        f"Unsupported listener type: {listener.listener_type}"
                    )

                thread.start()
            except Exception as exc:
                listener.status = "error"
                listener.error_message = str(exc)
                db.session.commit()
                logger.exception(
                    "Failed to start listener %s (type: %s)",
                    listener_id,
                    listener.listener_type,
                )
                return {"ok": False, "error": str(exc)}

            with self._lock:
                self._threads[listener_id] = thread

            listener.status = "running"
            listener.error_message = None
            listener.pid = threading.current_thread().ident
            listener.last_started_at = _utcnow()
            db.session.commit()

            logger.info(
                "Listener %s (%s) started on %s:%s",
                listener_id,
                listener.listener_type,
                host,
                port,
            )
            return {
                "ok": True,
                "message": f"{listener.listener_type.upper()} Listener started on {host}:{port}",
            }

    def stop_listener(self, listener_id: int) -> dict:
        """Stop a running listener."""
        from models import db, Listener as LModel

        with self._lock:
            thread = self._threads.pop(listener_id, None)

        if thread is None:
            # Still update DB status if it says running
            with self._app.app_context():
                listener = db.session.get(LModel, listener_id)
                if listener and listener.status == "running":
                    listener.status = "stopped"
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
                listener.status = "stopped"
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
            to_start = LModel.query.filter_by(status="running").all()
            for lsn in to_start:
                logger.info("Auto-starting listener %s (%s)", lsn.id, lsn.name)
                result = self.start_listener(lsn.id)
                if not result.get("ok"):
                    logger.warning(
                        "Auto-start failed for %s: %s", lsn.id, result.get("error")
                    )

    def shutdown_all(self):
        """Gracefully stop all running listeners."""
        with self._lock:
            ids = list(self._threads.keys())
        for lid in ids:
            self.stop_listener(lid)
        logger.info("All listeners shut down")
