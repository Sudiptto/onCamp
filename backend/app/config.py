import os
from datetime import timedelta


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///oncamp_dev.db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # HTTP-only so JavaScript can't read the session cookie.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Client ID from the Google Cloud Console. Tokens made for any other app get rejected.
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

    # How many days ahead logged out people can see. Signing in shows the rest.
    ANON_EVENT_DAYS = int(os.getenv("ANON_EVENT_DAYS", "7"))

    # Per-IP limit for every /api route. memory:// is fine for one dev server,
    # use a shared store like redis:// if this ever runs on more than one process.
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "1") == "1"
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "120 per minute")
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config():
    environment = os.getenv("APP_ENV", "development")
    return config.get(environment, config["default"])
