from flask import Flask

from .api import api_bp
from .config import get_config
from .extensions import cors, db
from .models import Club, Event


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config())

    db.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    app.register_blueprint(api_bp)

    with app.app_context():
        db.create_all()

    return app
