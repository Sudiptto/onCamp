import os

from flask import Flask, jsonify, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from .api import api_bp
from .config import get_config
from .extensions import cors, db, limiter
from . import models  # noqa: F401  (importing registers the tables with SQLAlchemy)

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config())
    app.config["FRONTEND_DIST_DIR"] = os.path.abspath(
        os.path.join(app.root_path, "..", "frontend_dist")
    )
    app.config.update(config_overrides or {})

    if os.getenv("TRUST_PROXY") == "1":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    if (
        os.getenv("APP_ENV") == "production"
        and not os.getenv("SECRET_KEY")
        and not (config_overrides or {}).get("SECRET_KEY")
    ):
        raise RuntimeError("SECRET_KEY must be set in production.")

    if (
        os.getenv("APP_ENV") == "production"
        and not os.getenv("DATABASE_URL")
        and not (config_overrides or {}).get("SQLALCHEMY_DATABASE_URI")
    ):
        raise RuntimeError("DATABASE_URL must be set in production.")

    db.init_app(app)
    limiter.init_app(app)

    origins = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
        if origin.strip()
    ]
    cors.init_app(app, resources={r"/api/*": {"origins": origins}}, supports_credentials=True)

    app.register_blueprint(api_bp)

    @app.get("/")
    def frontend_index():
        return send_from_directory(app.config["FRONTEND_DIST_DIR"], "index.html")

    @app.get("/assets/<path:filename>")
    def frontend_assets(filename):
        return send_from_directory(
            os.path.join(app.config["FRONTEND_DIST_DIR"], "assets"), filename
        )

    @app.errorhandler(429)
    def too_many_requests(_error):
        return jsonify({"error": "Too many requests, please slow down."}), 429

    if app.config.get("AUTO_CREATE_TABLES", True):
        with app.app_context():
            db.create_all()

    return app
