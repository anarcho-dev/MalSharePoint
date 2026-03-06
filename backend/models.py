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
