import os
import tempfile
import uuid

import pytest
from flask import g

from config import normalize_database_url
from gaminghub import create_app
from gaminghub.database.database import db as _db
from gaminghub.database.database import bcrypt


# Point the suite at another database (CI runs it against PostgreSQL):
#   TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/cognexa_test pytest
# Every test then creates the schema at start and drops it at the end, so
# the database must be a disposable one. Unset, each test gets its own
# SQLite file (see _make_test_config).
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()


def _make_test_config(db_path):
    """
    A fresh class per test, each pointed at its own SQLite file. This
    was originally in-memory SQLite (a shared "sqlite://" URI + StaticPool),
    which turned out not to be reliably isolated: db is a module-level
    singleton (gaminghub/database/database.py) reused by every test's
    create_app() call, and disposing the engine between tests still left
    some runs seeing another test's leftover rows once the full suite ran
    across multiple files (a single test or a single file in isolation
    never showed it -- only certain cross-file orderings did, which is
    what made it worth tracking down rather than shrugging off). A real
    per-test file sidesteps whatever SQLAlchemy-level caching caused that:
    two different paths cannot accidentally share a connection.
    """

    class _TestConfig:
        TESTING = True
        SECRET_KEY = "test-secret-key-not-for-production"
        SQLALCHEMY_DATABASE_URI = normalize_database_url(TEST_DATABASE_URL) if TEST_DATABASE_URL else f"sqlite:///{db_path}"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        WTF_CSRF_ENABLED = False
        RATELIMIT_ENABLED = False
        RATELIMIT_STORAGE_URI = "memory://"
        MAIL_BACKEND = "memory"
        APP_BASE_URL = "http://localhost"
        APP_ENV = "testing"

    return _TestConfig


def _isolate_requests(application):
    """
    These fixtures hold one app context open for the whole test, and
    Flask reuses an already-pushed app context for every test-client
    request -- so flask.g, where Flask-Login caches the current user,
    would carry over from one request (or one test client) to the next.
    Real requests each get a fresh g; this restores that, so session
    invalidation is tested the way it behaves in production.
    """

    @application.before_request
    def _fresh_login_user():
        g.pop("_login_user", None)


@pytest.fixture
def app():
    db_path = os.path.join(tempfile.gettempdir(), f"gaminghub_test_{uuid.uuid4().hex}.sqlite")
    application = create_app(_make_test_config(db_path))
    _isolate_requests(application)

    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        if TEST_DATABASE_URL:
            _db.drop_all()
        _db.engine.dispose()

    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def rate_limited_app():
    """A separate app instance with RATELIMIT_ENABLED left on, for the
    couple of tests that specifically verify rate limiting -- kept apart
    from the default `app` fixture so every other test isn't stuck
    reasoning about request budgets it doesn't care about."""

    db_path = os.path.join(tempfile.gettempdir(), f"gaminghub_test_{uuid.uuid4().hex}.sqlite")
    config = _make_test_config(db_path)
    config.RATELIMIT_ENABLED = True
    application = create_app(config)
    _isolate_requests(application)

    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        if TEST_DATABASE_URL:
            _db.drop_all()
        _db.engine.dispose()

    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def rate_limited_client(rate_limited_app):
    return rate_limited_app.test_client()


@pytest.fixture
def db(app):
    return _db


# ------------------------------------------------------------- factories
#
# Each of these returns a function so a test can create exactly the
# entities it needs, with sensible defaults for everything it doesn't
# care about. The in-memory DB starts completely empty -- there's no
# seeded catalog like the real dev database has.

@pytest.fixture
def make_user(db):
    from gaminghub.models.user import User

    def _make(username="testuser", email=None, password="testpass123", role="player", **kwargs):
        user = User(
            username=username,
            email=email or f"{username}@test.com",
            password=bcrypt.generate_password_hash(password).decode("utf-8"),
            role=role,
            **kwargs
        )
        db.session.add(user)
        db.session.commit()
        return user

    return _make


@pytest.fixture
def make_game(db):
    from gaminghub.models.game import Game

    def _make(name="Test Game", slug="test-game", category="classic-arcade", icon="🎮", is_active=True, **kwargs):
        game = Game(name=name, slug=slug, category=category, icon=icon, is_active=is_active, **kwargs)
        db.session.add(game)
        db.session.commit()
        return game

    return _make


@pytest.fixture
def make_achievement(db):
    from gaminghub.models.achievement import Achievement

    def _make(name, title=None, description="", badge="🏆", coin_reward=0, xp_reward=0):
        achievement = Achievement(
            name=name, title=title or name, description=description,
            badge=badge, coin_reward=coin_reward, xp_reward=xp_reward
        )
        db.session.add(achievement)
        db.session.commit()
        return achievement

    return _make


@pytest.fixture
def login_as(client):
    """Logs the test client in as the given user directly through Flask-
    Login's session key, bypassing the actual /login form -- route tests
    that need an authenticated session shouldn't have to re-drive the
    login flow every time; that flow gets its own dedicated tests."""

    def _login(user):
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True
        return client

    return _login


@pytest.fixture
def make_shop_item(db):
    from gaminghub.models.shop_item import ShopItem

    def _make(name="Test Item", item_type="avatar", cost=50, asset="test.png", is_active=True):
        item = ShopItem(name=name, item_type=item_type, cost=cost, asset=asset, is_active=is_active)
        db.session.add(item)
        db.session.commit()
        return item

    return _make
