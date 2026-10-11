import os

from flask import Flask, jsonify

from .api import api_bp
from .config import get_config
from .extensions import cors, db, limiter
from . import models  # noqa: F401  (importing registers the tables with SQLAlchemy)

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config())
    app.config.update(config_overrides or {})

    db.init_app(app)
    limiter.init_app(app)

    origins = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
        if origin.strip()
    ]
    cors.init_app(app, resources={r"/api/*": {"origins": origins}})

    app.register_blueprint(api_bp)

    @app.errorhandler(429)
    def too_many_requests(_error):
        return jsonify({"error": "Too many requests, please slow down."}), 429

    with app.app_context():
        db.create_all()

    return app
