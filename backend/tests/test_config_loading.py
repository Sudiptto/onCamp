import runpy
from pathlib import Path

import dotenv
import pytest

from app import create_app
from app.extensions import db


def test_root_env_is_loaded_before_database_config(monkeypatch):
    config_path = Path(__file__).resolve().parents[1] / "app" / "config.py"
    loaded_paths = []

    def load_config(path):
        loaded_paths.append(path)
        monkeypatch.setenv("DATABASE_URL", "sqlite:///calendar-test.db")

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(dotenv, "load_dotenv", load_config)
    config = runpy.run_path(str(config_path))
    assert loaded_paths == [config_path.parents[2] / ".env"]
    assert config["BaseConfig"].SQLALCHEMY_DATABASE_URI == "sqlite:///calendar-test.db"


def test_production_requires_a_database_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL must be set"):
        create_app({"SECRET_KEY": "test-key"})


def test_production_does_not_create_tables_on_startup(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db, "create_all", lambda: pytest.fail("unexpected schema creation"))

    app = create_app({
        "SECRET_KEY": "test-key",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "RATELIMIT_ENABLED": False,
    })

    assert app.config["AUTO_CREATE_TABLES"] is False


def test_trusted_proxy_uses_only_the_rightmost_forwarded_address(monkeypatch):
    from flask import request

    monkeypatch.setenv("TRUST_PROXY", "1")
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-key",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "AUTO_CREATE_TABLES": False,
        "RATELIMIT_ENABLED": False,
    })

    @app.get("/proxy-test")
    def proxy_test():
        return request.remote_addr

    response = app.test_client().get(
        "/proxy-test",
        headers={"X-Forwarded-For": "203.0.113.1, 198.51.100.2"},
    )
    assert response.get_data(as_text=True) == "198.51.100.2"
