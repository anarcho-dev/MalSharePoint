from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role:
    USER = 'user'
    ADMIN = 'admin'
    READONLY = 'readonly'


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=Role.USER)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    must_change_password = db.Column(db.Boolean, server_default='0', default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False)
    last_login = db.Column(db.DateTime(timezone=True))

    uploads = db.relationship('File', backref='uploader', lazy='dynamic',
                              foreign_keys='File.uploaded_by')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic',
                                 foreign_keys='AuditLog.user_id')

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'must_change_password': self.must_change_password,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }


class File(db.Model):
    __tablename__ = 'files'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)           # stored UUID name
    original_filename = db.Column(db.String(256), nullable=False)  # original name
    file_hash_sha256 = db.Column(db.String(64), nullable=False, index=True)
    file_size = db.Column(db.BigInteger, nullable=False)
    mime_type = db.Column(db.String(128))
    description = db.Column(db.Text)
    tags = db.Column(db.String(512))
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    download_count = db.Column(db.Integer, default=0, nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    upload_date = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.original_filename,
            'sha256': self.file_hash_sha256,
            'size': self.file_size,
            'mime_type': self.mime_type,
            'description': self.description,
            'tags': self.tags.split(',') if self.tags else [],
            'is_public': self.is_public,
            'download_count': self.download_count,
            'uploaded_by': self.uploaded_by,
            'upload_date': self.upload_date.isoformat(),
        }


class Snippet(db.Model):
    __tablename__ = 'snippets'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    title = db.Column(db.String(128), nullable=False)
    content = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(32), default='text')
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'slug': self.slug,
            'title': self.title,
            'language': self.language,
            'is_public': self.is_public,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'raw_url': f"/api/snippets/{self.slug}/raw"
        }


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(64), nullable=False)
    target = db.Column(db.String(256))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'target': self.target,
            'details': self.details,
            'ip_address': self.ip_address,
            'timestamp': self.timestamp.isoformat(),
        }


class ServerConfig(db.Model):
    __tablename__ = 'server_config'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(128), unique=True, nullable=False)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    @classmethod
    def get(cls, key, default=None):
        entry = cls.query.filter_by(key=key).first()
        return entry.value if entry else default

    @classmethod
    def set(cls, key: str, value: str) -> None:
        entry = cls.query.filter_by(key=key).first()
        if entry:
            entry.value = value
            entry.updated_at = _utcnow()
        else:
            entry = cls(key=key, value=str(value))
            db.session.add(entry)
        db.session.commit()


# ---------------------------------------------------------------------------
# Listener Subsystem Models
# ---------------------------------------------------------------------------

class ListenerProfile(db.Model):
    __tablename__ = 'listener_profiles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    description = db.Column(db.Text, default='')
    server_header = db.Column(db.String(256), default='Apache/2.4.54 (Ubuntu)')
    custom_headers = db.Column(db.Text, default='{}')          # JSON
    default_response_body = db.Column(db.Text, default='<html><body><h1>It works!</h1></body></html>')
    default_content_type = db.Column(db.String(128), default='text/html')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    listeners = db.relationship('Listener', backref='profile', lazy='dynamic')

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'server_header': self.server_header,
            'custom_headers': json.loads(self.custom_headers) if self.custom_headers else {},
            'default_response_body': self.default_response_body,
            'default_content_type': self.default_content_type,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
        }


class Listener(db.Model):
    __tablename__ = 'listeners'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    listener_type = db.Column(db.String(32), nullable=False, default='http')  # http | https
    bind_address = db.Column(db.String(45), nullable=False, default='0.0.0.0')
    bind_port = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='stopped')  # stopped|starting|running|error
    tls_cert_path = db.Column(db.String(512), nullable=True)
    tls_key_path = db.Column(db.String(512), nullable=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('listener_profiles.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pid = db.Column(db.Integer, nullable=True)
    last_started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_stopped_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)
    error_message = db.Column(db.Text, nullable=True)

    callbacks = db.relationship('Callback', backref='listener', lazy='dynamic')
    staged_payloads = db.relationship('StagedPayload', backref='listener', lazy='dynamic')
    agents = db.relationship('Agent', backref='listener', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'listener_type': self.listener_type,
            'bind_address': self.bind_address,
            'bind_port': self.bind_port,
            'status': self.status,
            'tls_cert_path': self.tls_cert_path,
            'tls_key_path': self.tls_key_path,
            'profile_id': self.profile_id,
            'profile_name': self.profile.name if self.profile else None,
            'created_by': self.created_by,
            'pid': self.pid,
            'last_started_at': self.last_started_at.isoformat() if self.last_started_at else None,
            'last_stopped_at': self.last_stopped_at.isoformat() if self.last_stopped_at else None,
            'created_at': self.created_at.isoformat(),
            'error_message': self.error_message,
            'callback_count': self.callbacks.count(),
            'agent_count': self.agents.count(),
            'staged_count': self.staged_payloads.filter_by(is_active=True).count(),
        }


class Callback(db.Model):
    __tablename__ = 'callbacks'

    id = db.Column(db.Integer, primary_key=True)
    listener_id = db.Column(db.Integer, db.ForeignKey('listeners.id'), nullable=False)
    source_ip = db.Column(db.String(45), nullable=False)
    source_port = db.Column(db.Integer, nullable=True)
    hostname = db.Column(db.String(256), nullable=True)
    user_agent = db.Column(db.String(512), default='')
    request_method = db.Column(db.String(10), nullable=False)
    request_path = db.Column(db.String(1024), nullable=False)
    request_headers = db.Column(db.Text, default='{}')   # JSON
    request_body = db.Column(db.Text, nullable=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=_utcnow)
    metadata_json = db.Column(db.Text, nullable=True)     # JSON

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'listener_id': self.listener_id,
            'source_ip': self.source_ip,
            'source_port': self.source_port,
            'hostname': self.hostname,
            'user_agent': self.user_agent,
            'request_method': self.request_method,
            'request_path': self.request_path,
            'request_headers': json.loads(self.request_headers) if self.request_headers else {},
            'request_body': self.request_body,
            'file_id': self.file_id,
            'timestamp': self.timestamp.isoformat(),
            'metadata': json.loads(self.metadata_json) if self.metadata_json else None,
        }


class StagedPayload(db.Model):
    __tablename__ = 'staged_payloads'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    listener_id = db.Column(db.Integer, db.ForeignKey('listeners.id'), nullable=False)
    payload_type = db.Column(db.String(32), nullable=False, default='raw')  # raw|ps1|bat|vbs|hta
    content = db.Column(db.Text, nullable=False)
    content_hash = db.Column(db.String(64), nullable=False)
    stage_path = db.Column(db.String(256), nullable=False)       # e.g. /update.js
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    download_count = db.Column(db.Integer, default=0, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'listener_id': self.listener_id,
            'payload_type': self.payload_type,
            'content_hash': self.content_hash,
            'stage_path': self.stage_path,
            'is_active': self.is_active,
            'download_count': self.download_count,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# C2 Agent Models
# ---------------------------------------------------------------------------

class Agent(db.Model):
    __tablename__ = 'agents'

    id = db.Column(db.String(36), primary_key=True)                # UUID
    hostname = db.Column(db.String(256), nullable=True)
    username = db.Column(db.String(256), nullable=True)
    os_info = db.Column(db.String(512), nullable=True)
    internal_ip = db.Column(db.String(45), nullable=True)
    external_ip = db.Column(db.String(45), nullable=True)
    listener_id = db.Column(db.Integer, db.ForeignKey('listeners.id'), nullable=True)
    sleep_interval = db.Column(db.Integer, default=5, nullable=False)
    jitter = db.Column(db.Integer, default=10, nullable=False)
    status = db.Column(db.String(20), default='active', nullable=False)  # active|dormant|dead|disconnected
    last_seen = db.Column(db.DateTime(timezone=True), default=_utcnow)
    first_seen = db.Column(db.DateTime(timezone=True), default=_utcnow)
    metadata_json = db.Column(db.Text, nullable=True)              # JSON

    tasks = db.relationship('AgentTask', backref='agent', lazy='dynamic',
                            order_by='AgentTask.created_at.desc()')

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'hostname': self.hostname,
            'username': self.username,
            'os_info': self.os_info,
            'internal_ip': self.internal_ip,
            'external_ip': self.external_ip,
            'listener_id': self.listener_id,
            'sleep_interval': self.sleep_interval,
            'jitter': self.jitter,
            'status': self.status,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
            'metadata': json.loads(self.metadata_json) if self.metadata_json else None,
            'task_count': self.tasks.count(),
        }


class AgentTask(db.Model):
    __tablename__ = 'agent_tasks'

    id = db.Column(db.String(36), primary_key=True)                # UUID
    agent_id = db.Column(db.String(36), db.ForeignKey('agents.id'), nullable=False)
    command = db.Column(db.Text, nullable=False)
    task_type = db.Column(db.String(32), default='shell', nullable=False)
    status = db.Column(db.String(20), default='queued', nullable=False)  # queued|sent|completed|failed
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)
    sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    result = db.Column(db.Text, nullable=True)
    success = db.Column(db.Boolean, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'agent_id': self.agent_id,
            'command': self.command,
            'task_type': self.task_type,
            'status': self.status,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'result': self.result,
            'success': self.success,
        }
