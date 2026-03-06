import os
import atexit
import logging

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
from routes.exploits import exploits_bp
from routes.listeners import listeners_bp
from routes.c2 import c2_bp
from routes.agents import agents_bp
from listener import listener_bp
from listeners import ListenerManager

logger = logging.getLogger(__name__)

# Singleton listener manager shared across the app
listener_manager = ListenerManager()


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Extensions
    cors_origins = os.environ.get("CORS_ORIGINS", "*")
    CORS(app, resources={r"/api/*": {"origins": cors_origins}})
    db.init_app(app)
    Migrate(app, db)
    JWTManager(app)

    # Listener Manager
    listener_manager.init_app(app)

    # Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(snippets_bp)
    app.register_blueprint(exploits_bp)
    app.register_blueprint(listener_bp)      # legacy /api/l/* endpoints
    app.register_blueprint(listeners_bp)     # new /api/listeners/* CRUD + lifecycle
    app.register_blueprint(c2_bp)            # /api/c2/* agent-facing C2
    app.register_blueprint(agents_bp)        # /api/admin/agents/* management

    @app.route("/api/health", methods=["GET"])
    def health_check():
        try:
            db.session.execute(text("SELECT 1"))
            db_status = "healthy"
        except Exception as exc:  # noqa: BLE001
            db_status = f"unhealthy: {exc}"
        overall = "healthy" if db_status == "healthy" else "degraded"
        return jsonify({"status": overall, "database": db_status}), 200


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
        if "users" in insp.get_table_names():
            existing_cols = [c["name"] for c in insp.get_columns("users")]
            if "must_change_password" not in existing_cols:
                db.session.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 0 NOT NULL"
                    )
                )
                db.session.commit()

        # Seed default admin user on first run
        if not User.query.filter_by(username="admin").first():
            seed = User(
                username="admin",
                email="admin@malsharepoint.local",
                role=Role.ADMIN,
                must_change_password=True,
            )
            seed.set_password("password123")
            db.session.add(seed)
            db.session.commit()
            app.logger.info("Seeded default admin user 'admin'")

        # Seed default listener profiles
        from models import ListenerProfile
        if ListenerProfile.query.count() == 0:
            for pdata in [
                {
                    'name': 'Apache Default',
                    'server_header': 'Apache/2.4.54 (Ubuntu)',
                    'default_response_body': '<html><body><h1>It works!</h1></body></html>',
                },
                {
                    'name': 'Nginx',
                    'server_header': 'nginx/1.24.0',
                    'default_response_body': '<html><head><title>Welcome to nginx!</title></head><body><h1>Welcome to nginx!</h1></body></html>',
                },
                {
                    'name': 'IIS 10',
                    'server_header': 'Microsoft-IIS/10.0',
                    'default_response_body': '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"><html><head><title>IIS Windows Server</title></head><body><img src="iisstart.png" alt="IIS" /></body></html>',
                },
            ]:
                p = ListenerProfile(name=pdata['name'], server_header=pdata['server_header'],
                                    default_response_body=pdata['default_response_body'])
                db.session.add(p)
            db.session.commit()
            app.logger.info("Seeded default listener profiles")

        # Auto-start listeners that were running before shutdown
        listener_manager.auto_start()

    # Graceful shutdown
    atexit.register(listener_manager.shutdown_all)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5005)
