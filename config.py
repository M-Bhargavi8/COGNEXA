"""
Environment-driven configuration.

APP_ENV picks the class: "development" (default for `python app.py`),
"production" (default for wsgi.py, the production entry point) or
"testing". Every value a deployment needs to change comes from an
environment variable -- see .env.example and docs/DEPLOYMENT.md for the
full reference. ProductionConfig.validate() refuses to start the app
with an unsafe or incomplete production configuration instead of
silently falling back to a development default.
"""

import os
import secrets
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DEFAULT_SQLITE_PATH = os.path.join(BASE_DIR, "gaminghub", "database", "gaming.db")


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_int(name, default):
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def normalize_database_url(url):
    """Hosting providers commonly hand out postgres:// URLs, which
    SQLAlchemy 2 no longer accepts -- it needs the dialect+driver form.
    psycopg (v3) is the driver documented in docs/DEPLOYMENT.md."""

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _database_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    return normalize_database_url(url) if url else "sqlite:///" + DEFAULT_SQLITE_PATH


def _get_or_create_dev_secret_key():
    """
    A real SECRET_KEY signs both session cookies and CSRF tokens -- a
    hardcoded one checked into source control means anyone who reads the
    code can forge either. SECRET_KEY in the environment always wins;
    otherwise (development only) a random key is generated once and
    persisted in the gitignored instance folder, so dev sessions survive
    restarts without ever committing a real secret. Production never
    takes this path -- ProductionConfig requires SECRET_KEY explicitly.
    """

    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key

    os.makedirs(INSTANCE_DIR, exist_ok=True)
    key_path = os.path.join(INSTANCE_DIR, "secret_key")

    if os.path.exists(key_path):
        with open(key_path, "r") as f:
            return f.read().strip()

    key = secrets.token_hex(32)
    with open(key_path, "w") as f:
        f.write(key)

    return key


class BaseConfig:
    """Defaults shared by every environment. create_app() always loads
    this first, so a config class (including the test suite's) only has
    to set what it changes."""

    APP_ENV = "development"
    BASE_DIR = BASE_DIR
    INSTANCE_DIR = INSTANCE_DIR

    SECRET_KEY = os.environ.get("SECRET_KEY")

    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # The one trusted origin used to build links that leave the app
    # (password-reset and verification emails). Never derived from the
    # request's Host header, which a client controls.
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/")

    # No feature accepts uploads; anything bigger than this is not a
    # legitimate form post or API call.
    MAX_CONTENT_LENGTH = 1024 * 1024

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)

    REMEMBER_COOKIE_DURATION = timedelta(days=env_int("REMEMBER_COOKIE_DAYS", 14))
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)

    # Flask-Limiter. memory:// is per-process: fine for one process,
    # wrong once there are several workers or instances (each would keep
    # its own counters). Production must point this at shared storage
    # such as redis://, or explicitly opt in to memory for a single
    # process via RATELIMIT_ALLOW_MEMORY_STORAGE.
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_ALLOW_MEMORY_STORAGE = env_bool("RATELIMIT_ALLOW_MEMORY_STORAGE", False)
    RATELIMIT_HEADERS_ENABLED = True
    # If the shared storage (Redis) becomes unreachable, keep enforcing
    # the same limits per process instead of failing every request --
    # still throttled, just counted locally until Redis is back. /healthz
    # reports "degraded" meanwhile so monitoring notices.
    RATELIMIT_IN_MEMORY_FALLBACK_ENABLED = env_bool("RATELIMIT_IN_MEMORY_FALLBACK_ENABLED", True)

    # Number of reverse proxies in front of the app whose X-Forwarded-*
    # headers should be trusted (0 = none). Needed for correct client IPs
    # in rate limiting and for request.is_secure behind a TLS proxy.
    TRUSTED_PROXY_COUNT = env_int("TRUSTED_PROXY_COUNT", 0)

    # Email: "console" logs messages (development only), "smtp" sends
    # them, "memory" keeps them in a list (tests).
    MAIL_BACKEND = os.environ.get("MAIL_BACKEND", "console").strip().lower()
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = env_int("MAIL_PORT", 587)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_USE_TLS = env_bool("MAIL_USE_TLS", True)
    MAIL_USE_SSL = env_bool("MAIL_USE_SSL", False)
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "COGNEXA <no-reply@localhost>")
    MAIL_TIMEOUT = env_int("MAIL_TIMEOUT", 10)

    # When on, an account can't log in (or get an API token) until its
    # email address is verified. Off by default so accounts created
    # before verification existed keep working; they see a prompt to
    # verify instead.
    EMAIL_VERIFICATION_REQUIRED = env_bool("EMAIL_VERIFICATION_REQUIRED", False)
    EMAIL_VERIFICATION_TOKEN_MAX_AGE = env_int("EMAIL_VERIFICATION_TOKEN_MAX_AGE", 48 * 3600)
    PASSWORD_RESET_TOKEN_MAX_AGE = env_int("PASSWORD_RESET_TOKEN_MAX_AGE", 3600)

    API_TOKEN_TTL_DAYS = env_int("API_TOKEN_TTL_DAYS", 30)

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

    @classmethod
    def validate(cls, config):
        """Returns a list of problems; empty means the config is usable."""
        return []


class DevelopmentConfig(BaseConfig):
    APP_ENV = "development"
    SECRET_KEY = _get_or_create_dev_secret_key() if os.environ.get("APP_ENV", "development") == "development" else None


class TestingConfig(BaseConfig):
    APP_ENV = "testing"
    TESTING = True
    SECRET_KEY = "test-secret-key-not-for-production"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    MAIL_BACKEND = "memory"
    APP_BASE_URL = "http://localhost"


class ProductionConfig(BaseConfig):
    APP_ENV = "production"
    DEBUG = False
    TESTING = False

    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
    REMEMBER_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
    PREFERRED_URL_SCHEME = "https"

    MAIL_BACKEND = os.environ.get("MAIL_BACKEND", "smtp").strip().lower()

    @classmethod
    def validate(cls, config):
        problems = []

        secret = config.get("SECRET_KEY") or ""
        if len(secret) < 32:
            problems.append("SECRET_KEY must be set to a random value of at least 32 characters.")

        if not os.environ.get("DATABASE_URL", "").strip():
            problems.append("DATABASE_URL must be set explicitly in production.")

        if not config.get("APP_BASE_URL", "").startswith("https://"):
            problems.append("APP_BASE_URL must be the public https:// origin of the app.")

        if config.get("RATELIMIT_STORAGE_URI", "").startswith("memory") and not config.get("RATELIMIT_ALLOW_MEMORY_STORAGE"):
            problems.append(
                "RATELIMIT_STORAGE_URI must point at shared storage (e.g. redis://...), "
                "or set RATELIMIT_ALLOW_MEMORY_STORAGE=1 for a single-process deployment."
            )

        backend = config.get("MAIL_BACKEND")
        if backend == "console":
            problems.append("MAIL_BACKEND=console would write reset links to the log; use smtp in production.")
        elif backend == "smtp":
            if not config.get("MAIL_SERVER"):
                problems.append("MAIL_SERVER must be set when MAIL_BACKEND=smtp.")
            if "localhost" in (config.get("MAIL_DEFAULT_SENDER") or ""):
                problems.append("MAIL_DEFAULT_SENDER must be a real sender address.")
        elif backend not in ("smtp", "disabled"):
            problems.append(f"Unknown MAIL_BACKEND {backend!r} (expected smtp or disabled).")

        if backend == "disabled" and config.get("EMAIL_VERIFICATION_REQUIRED"):
            problems.append("EMAIL_VERIFICATION_REQUIRED needs a working MAIL_BACKEND.")

        if config.get("DEBUG"):
            problems.append("DEBUG must be off in production.")

        return problems


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(env=None):
    env = (env or os.environ.get("APP_ENV") or "development").strip().lower()
    if env not in CONFIGS:
        raise RuntimeError(f"Unknown APP_ENV {env!r}; expected one of {sorted(CONFIGS)}.")
    return CONFIGS[env]


# Backwards-compatible name for scripts that import Config directly.
Config = DevelopmentConfig
