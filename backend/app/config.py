import os


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///oncamp_dev.db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Per-IP limit for every /api route. memory:// is fine for one dev server,
    # use a shared store like redis:// if this ever runs on more than one process.
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "1") == "1"
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "120 per minute")
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config():
    environment = os.getenv("APP_ENV", "development")
    return config.get(environment, config["default"])
