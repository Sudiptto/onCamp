import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app():
    test_app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "RATELIMIT_ENABLED": False,
        "AUTO_CREATE_TABLES": False,
        "GOOGLE_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
        "ANON_EVENT_DAYS": 7,
    })
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
