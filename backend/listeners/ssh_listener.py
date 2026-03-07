import logging
import socket
import threading
from datetime import datetime, timezone

import paramiko

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc)


class SSHServer(paramiko.ServerInterface):
    def __init__(self, listener_id, app_context, banner="SSH-2.0-OpenSSH_8.2p1"):
        self.listener_id = listener_id
        self.app_context = app_context
        self.banner = banner
        self.event = threading.Event()

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username, password):
        # Log attempt (simplified callback simulation)
        logger.info(
            "SSH Auth Attempt on listener %s: %s:%s",
            self.listener_id,
            username,
            password,
        )
        # For a C2, we might accept anything or specific creds
        return paramiko.AUTH_SUCCESSFUL

    def get_allowed_auths(self, username):
        return "password"


class SSHListenerThread(threading.Thread):
    def __init__(self, listener_id, host, port, options, app):
        super().__init__(daemon=True, name=f"ssh-listener-{listener_id}")
        self.listener_id = listener_id
        self.host = host
        self.port = port
        self.options = options
        self.app = app
        self.active = True
        self.sock = None

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.host, self.port))
            self.sock.listen(100)
            self.sock.settimeout(1.0)

            logger.info(
                "SSH Listener %s started on %s:%s",
                self.listener_id,
                self.host,
                self.port,
            )

            # Load or generate host key
            key_path = self.options.get("key_path", "instance/ssh_host_rsa_key")
            try:
                host_key = paramiko.RSAKey.from_private_key_file(key_path)
            except Exception:
                logger.warning(
                    "SSH Key not found at %s, generating temporary key...", key_path
                )
                host_key = paramiko.RSAKey.generate(2048)

            while self.active:
                try:
                    client, addr = self.sock.accept()
                except socket.timeout:
                    continue

                logger.info(
                    "SSH Connection from %s to listener %s", addr, self.listener_id
                )

                transport = paramiko.Transport(client)
                transport.add_server_key(host_key)

                server = SSHServer(
                    self.listener_id,
                    self.app.app_context(),
                    banner=self.options.get("banner", "SSH-2.0-OpenSSH_8.2p1"),
                )

                try:
                    transport.start_server(server=server)
                except paramiko.SSHException:
                    logger.error("SSH negotiation failed.")
                    continue

        except Exception as e:
            logger.exception("SSH Listener %s failed: %s", self.listener_id, e)
        finally:
            if self.sock:
                self.sock.close()

    def shutdown(self):
        self.active = False
        if self.sock:
            # Wake up from accept()
            try:
                temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                temp_sock.connect((self.host, self.port))
                temp_sock.close()
            except:
                pass
            self.sock.close()
