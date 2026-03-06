import uuid
from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from models import db, Snippet, AuditLog

snippets_bp = Blueprint('snippets', __name__, url_prefix='/api/snippets')


def _log(user_id, action, target=None, details=None, ip=None):
    entry = AuditLog(user_id=user_id, action=action, target=target,
                     details=details, ip_address=ip)
    db.session.add(entry)
    db.session.commit()


@snippets_bp.route('', methods=['GET'])
@jwt_required()
def list_snippets():
    user_id = int(get_jwt_identity())
    role = get_jwt().get('role')

    if role == 'admin':
        query = Snippet.query
    else:
        query = Snippet.query.filter(
            (Snippet.created_by == user_id) | (Snippet.is_public.is_(True))
        )

    snippets = query.order_by(Snippet.created_at.desc()).all()
    return jsonify([s.to_dict() for s in snippets]), 200


@snippets_bp.route('', methods=['POST'])
@jwt_required()
def create_snippet():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    title = data.get('title', '').strip()
    content = data.get('content', '')
    language = data.get('language', 'text')
    is_public = data.get('is_public', False)
    slug = data.get('slug', '').strip()

    if not title or not content:
        return jsonify({"error": "Title and content are required"}), 400

    # Generate slug if not provided
    if not slug:
        slug = uuid.uuid4().hex[:8]
    
    if Snippet.query.filter_by(slug=slug).first():
        return jsonify({"error": "Slug already in use"}), 409

    snippet = Snippet(
        slug=slug,
        title=title,
        content=content,
        language=language,
        is_public=is_public,
        created_by=user_id
    )
    db.session.add(snippet)
    db.session.commit()

    _log(user_id, 'create_snippet', target=slug, ip=request.remote_addr)
    return jsonify(snippet.to_dict()), 201


@snippets_bp.route('/<slug>/raw', methods=['GET'])
def get_raw_snippet(slug):
    """
    Serves the raw content of the snippet.
    Useful for: curl http://server/api/snippets/myscript/raw | bash
    """
    snippet = Snippet.query.filter_by(slug=slug).first_or_404()

    # If not public, we could require a token, but for simple delivery
    # we often rely on the secrecy of the slug or public flag.
    if not snippet.is_public:
        return jsonify({"error": "Access denied"}), 403

    # Log the access (useful for tracking if a payload was fetched)
    # We log with user_id=None since this is likely a public/tool access
    _log(None, 'fetch_snippet', target=slug, ip=request.remote_addr)

    return Response(snippet.content, mimetype='text/plain')