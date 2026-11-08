import runpy
from pathlib import Path

import dotenv


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
