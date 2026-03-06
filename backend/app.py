import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from sqlalchemy import text
from config import config
from models import db, User, Role
from routes.auth import auth_bp
from routes.files import files_bp
from routes.admin import admin_bp
from routes.snippets import snippets_bp


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Extensions
    cors_origins = os.environ.get('CORS_ORIGINS', '*')
    CORS(app, resources={r"/api/*": {"origins": cors_origins}})
    db.init_app(app)
    Migrate(app, db)
    JWTManager(app)

    # Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(snippets_bp)

    @app.route('/api/health', methods=['GET'])
    def health_check():
        try:
            db.session.execute(text('SELECT 1'))
            db_status = 'healthy'
        except Exception as exc:  # noqa: BLE001
            db_status = f'unhealthy: {exc}'
        overall = 'healthy' if db_status == 'healthy' else 'degraded'
        return jsonify({'status': overall, 'database': db_status}), 200

    @app.route('/api/c2/checkin', methods=['GET', 'POST'])
    def honeypot_c2():
        # Log the suspicious attempt with source IP
        app.logger.warning(f"Suspicious C2 checkin attempt from {request.remote_addr}")
        return jsonify({"status": "error", "message": "Invalid endpoint"}), 404

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "File too large"}), 413

    with app.app_context():
        db.create_all()

        # SQLite-compatible: add column if it doesn't exist yet
        from sqlalchemy import inspect as sa_inspect
        insp = sa_inspect(db.engine)
        if 'users' in insp.get_table_names():
            existing_cols = [c['name'] for c in insp.get_columns('users')]
            if 'must_change_password' not in existing_cols:
                db.session.execute(
                    text('ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 0 NOT NULL')
                )
                db.session.commit()

        # Seed default admin user on first run
        if not User.query.filter_by(username='admin').first():
            seed = User(
                username='admin',
                email='admin@malsharepoint.local',
                role=Role.ADMIN,
                must_change_password=True,
            )
            seed.set_password('password123')
            db.session.add(seed)
            db.session.commit()
            app.logger.info("Seeded default admin user 'admin'")

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5005)
