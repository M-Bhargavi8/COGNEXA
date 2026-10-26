"""
Regression tests for the production-hardening work: race conditions on
balance-changing operations, API token lifetime, production config
validation, the health check, security headers and safe redirects.
"""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.orm.attributes import set_committed_value

from gaminghub.database.database import db as _db
from gaminghub.models.api_token import ApiToken
from gaminghub.models.game_result import GameResult
from gaminghub.models.user import User
from gaminghub.models.user_inventory import UserInventory
from gaminghub.services import api_auth_service, game_service, reward_service, shop_service
from gaminghub.utils.security import is_safe_redirect_target


# ----------------------------------------------------------- races
#
# Each test makes the in-memory object stale behind SQLAlchemy's back --
# exactly the state a second, concurrent request is in when the first
# one has already committed. set_committed_value() gives the object an
# old value *without* marking it as a pending change (a plain assignment
# would be flushed back to the database, which a racing request never
# does).

class TestConcurrentSubmissions:

    def test_a_session_completed_by_another_request_pays_nothing(self, make_user, make_game):
        user = make_user()
        game = make_game(slug="guess-the-number")
        session = game_service.start_session(user, "guess-the-number")

        _db.session.execute(text("UPDATE game_sessions SET status = 'completed' WHERE id = :id"), {"id": session.id})
        _db.session.commit()
        set_committed_value(session, "status", "active")  # the losing request's stale view

        outcome = game_service.complete_session(session, user, outcome="win", xp=50, coins=50)

        assert outcome is None
        assert GameResult.query.count() == 0
        assert _db.session.get(User, user.id).coins == 100

    def test_purchase_cannot_spend_coins_already_spent(self, make_user, make_shop_item):
        user = make_user(coins=100)
        first = make_shop_item(name="A", asset="a.png", cost=100)
        second = make_shop_item(name="B", asset="b.png", cost=100)

        ok, _ = shop_service.purchase_item(user, first.id)
        assert ok

        set_committed_value(user, "coins", 100)  # stale balance from before the first purchase
        ok, message = shop_service.purchase_item(user, second.id)

        assert not ok and message == "Not enough coins."
        assert _db.session.get(User, user.id).coins == 0
        assert UserInventory.query.count() == 1

    def test_duplicate_ownership_race_refunds_the_debit(self, make_user, make_shop_item):
        user = make_user(coins=500)
        item = make_shop_item(cost=100)
        _db.session.add(UserInventory(user_id=user.id, shop_item_id=item.id))
        _db.session.commit()

        # Simulate the ownership check having passed in a racing request
        # by calling straight past it: insert collides on the unique key.
        from unittest import mock
        with mock.patch.object(shop_service.UserInventory, "query") as q:
            q.filter_by.return_value.first.return_value = None
            q.filter_by.return_value.with_entities.return_value.all.return_value = []
            ok, message = shop_service.purchase_item(user, item.id)

        assert not ok and message == "You already own this."
        assert _db.session.get(User, user.id).coins == 500

    def test_daily_claim_cannot_be_collected_twice(self, make_user):
        user = make_user(coins=0)

        ok, _, _ = reward_service.claim_daily_reward(user)
        assert ok

        set_committed_value(user, "last_claim", date.today() - timedelta(days=3))  # stale view
        ok, message, coins = reward_service.claim_daily_reward(user)

        assert not ok and coins == 0
        assert _db.session.get(User, user.id).coins == 20


# ------------------------------------------------------------- API tokens

class TestApiTokenLifetime:

    def test_issued_tokens_expire(self, client, make_user):
        make_user(email="api@test.com", password="correctpass1")

        resp = client.post("/api/auth/token", json={"email": "api@test.com", "password": "correctpass1"})

        assert resp.status_code == 201
        assert resp.get_json()["expires_at"]
        assert ApiToken.query.one().expires_at > datetime.utcnow() + timedelta(days=29)

    def test_expired_token_is_rejected(self, client, make_user):
        user = make_user()
        token = api_auth_service.issue_token(user)
        ApiToken.query.update({"expires_at": datetime.utcnow() - timedelta(seconds=1)})
        _db.session.commit()

        assert client.get("/api/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401

    def test_suspended_users_token_stops_working(self, client, make_user):
        user = make_user()
        token = api_auth_service.issue_token(user)
        user.status = "suspended"
        _db.session.commit()

        assert client.get("/api/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401

    def test_suspended_user_cannot_get_a_token(self, client, make_user):
        make_user(email="s@test.com", password="correctpass1", status="suspended")
        resp = client.post("/api/auth/token", json={"email": "s@test.com", "password": "correctpass1"})
        assert resp.status_code == 403

    def test_unverified_user_cannot_get_a_token_when_required(self, app, client, make_user):
        app.config["EMAIL_VERIFICATION_REQUIRED"] = True
        make_user(email="u@test.com", password="correctpass1")
        resp = client.post("/api/auth/token", json={"email": "u@test.com", "password": "correctpass1"})
        assert resp.status_code == 403

    @pytest.mark.parametrize("body", [None, [], "text", {"email": ["a"], "password": {"x": 1}}])
    def test_malformed_token_requests_are_a_clean_401(self, client, body):
        resp = client.post("/api/auth/token", json=body)
        assert resp.status_code == 401

    def test_api_405_is_json(self, client):
        resp = client.put("/api/me")
        assert resp.status_code == 405
        assert resp.get_json() == {"error": "Method not allowed."}


# ------------------------------------------------------------- config

class TestProductionConfig:

    def _problems(self, monkeypatch, **env):
        from config import ProductionConfig

        for key in ("DATABASE_URL",):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        good = {
            "SECRET_KEY": "s" * 64,
            "APP_BASE_URL": "https://cognexa.example",
            "RATELIMIT_STORAGE_URI": "redis://localhost:6379/0",
            "MAIL_BACKEND": "smtp",
            "MAIL_SERVER": "smtp.example",
            "MAIL_DEFAULT_SENDER": "COGNEXA <no-reply@cognexa.example>",
            "DEBUG": False,
        }
        return good, ProductionConfig.validate

    def test_a_complete_config_passes(self, monkeypatch):
        good, validate = self._problems(monkeypatch, DATABASE_URL="postgresql://u:p@db/cognexa")
        assert validate(good) == []

    @pytest.mark.parametrize("override,fragment", [
        ({"SECRET_KEY": "short"}, "SECRET_KEY"),
        ({"APP_BASE_URL": "http://cognexa.example"}, "APP_BASE_URL"),
        ({"RATELIMIT_STORAGE_URI": "memory://"}, "RATELIMIT_STORAGE_URI"),
        ({"MAIL_BACKEND": "console"}, "MAIL_BACKEND=console"),
        ({"MAIL_SERVER": ""}, "MAIL_SERVER"),
        ({"MAIL_DEFAULT_SENDER": "x <no-reply@localhost>"}, "MAIL_DEFAULT_SENDER"),
        ({"DEBUG": True}, "DEBUG"),
    ])
    def test_each_unsafe_setting_is_reported(self, monkeypatch, override, fragment):
        good, validate = self._problems(monkeypatch, DATABASE_URL="sqlite:////data/cognexa.db")
        problems = validate({**good, **override})
        assert any(fragment in p for p in problems), problems

    def test_database_url_is_required(self, monkeypatch):
        good, validate = self._problems(monkeypatch)
        assert any("DATABASE_URL" in p for p in validate(good))

    def test_memory_rate_limits_allowed_with_explicit_opt_in(self, monkeypatch):
        good, validate = self._problems(monkeypatch, DATABASE_URL="sqlite:////data/cognexa.db")
        assert validate({**good, "RATELIMIT_STORAGE_URI": "memory://", "RATELIMIT_ALLOW_MEMORY_STORAGE": True}) == []

    def test_create_app_refuses_an_unsafe_production_config(self, monkeypatch):
        from config import ProductionConfig
        from gaminghub import create_app

        monkeypatch.delenv("DATABASE_URL", raising=False)

        class Unsafe(ProductionConfig):
            SECRET_KEY = "short"

        with pytest.raises(RuntimeError, match="unsafe configuration"):
            create_app(Unsafe)

    def test_postgres_urls_are_normalised_for_sqlalchemy(self):
        from config import normalize_database_url

        assert normalize_database_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
        assert normalize_database_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
        assert normalize_database_url("sqlite:///x.db") == "sqlite:///x.db"

    def test_unknown_app_env_is_an_error(self):
        from config import get_config
        with pytest.raises(RuntimeError):
            get_config("staging-ish")


# --------------------------------------------------- health + headers

class TestHealthAndHeaders:

    def test_health_check_reports_ok_and_nothing_else(self, client):
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}

    def test_health_check_reports_database_failure_without_details(self, client, monkeypatch):
        def broken(*args, **kwargs):
            raise RuntimeError("connection refused to 10.0.0.5:5432")

        monkeypatch.setattr(_db.session, "execute", broken)
        resp = client.get("/healthz")

        assert resp.status_code == 503
        assert resp.get_json() == {"status": "unavailable"}
        assert b"10.0.0.5" not in resp.data

    def test_csp_forbids_inline_script(self, client):
        csp = client.get("/login").headers["Content-Security-Policy"]
        script_src = next(part for part in csp.split(";") if part.strip().startswith("script-src"))

        assert "'unsafe-inline'" not in script_src
        assert "object-src 'none'" in csp
        assert "form-action 'self'" in csp

    def test_templates_contain_no_executable_inline_script(self, app):
        import pathlib
        import re

        pattern = re.compile(r"<script(?![^>]*\bsrc=)(?![^>]*type=\"application/json\")[^>]*>", re.I)
        offenders = []
        for path in pathlib.Path(app.template_folder).rglob("*.html"):
            if pattern.search(path.read_text(encoding="utf-8")):
                offenders.append(path.name)
        assert offenders == []

    def test_pages_are_not_cached_but_static_files_can_be(self, client):
        assert client.get("/login").headers["Cache-Control"] == "no-store"
        assert "no-store" not in client.get("/static/css/cognexa.css").headers.get("Cache-Control", "")

    def test_session_cookie_is_httponly_and_samesite(self, client, make_user):
        make_user(email="cookie@test.com", password="correctpass1")
        resp = client.post("/login", data={"email": "cookie@test.com", "password": "correctpass1"})
        session_cookie = next(c for c in resp.headers.getlist("Set-Cookie") if c.startswith("session="))
        assert "HttpOnly" in session_cookie and "SameSite=Lax" in session_cookie

    def test_oversized_request_bodies_are_refused(self, client):
        resp = client.post("/api/auth/token", data="x" * (1024 * 1024 + 1), content_type="application/json")
        assert resp.status_code == 413

    def test_rate_limited_api_returns_json_429(self, rate_limited_client):
        statuses = [rate_limited_client.post("/api/auth/token", json={}).status_code for _ in range(11)]
        assert statuses[-1] == 429


class TestRateLimitsOnAccountRoutes:

    def test_forgot_password_posts_are_limited(self, rate_limited_client):
        statuses = [rate_limited_client.post("/forgot-password", data={"email": "a@test.com"}).status_code for _ in range(7)]
        assert statuses[:5] == [302] * 5
        assert statuses[5:] == [429, 429]

    def test_forgot_password_page_views_are_not_limited(self, rate_limited_client):
        assert all(rate_limited_client.get("/forgot-password").status_code == 200 for _ in range(8))


@pytest.mark.parametrize("target,expected", [
    ("/dashboard", True),
    ("/leaderboard?period=weekly#top", True),
    ("", False),
    (None, False),
    ("dashboard", False),
    ("//evil.example", False),
    ("/\\evil.example", False),
    ("https://evil.example/x", False),
    ("/ok\nSet-Cookie: x=1", False),
    ("/\x00", False),
])
def test_is_safe_redirect_target(target, expected):
    assert is_safe_redirect_target(target) is expected


class TestRateLimitStorageOutage:

    def _app(self, storage):
        import os
        import tempfile
        import uuid
        from tests.conftest import _make_test_config
        from gaminghub import create_app

        config = _make_test_config(os.path.join(tempfile.gettempdir(), f"gaminghub_rl_{uuid.uuid4().hex}.sqlite"))
        config.RATELIMIT_ENABLED = True
        config.RATELIMIT_STORAGE_URI = storage
        return create_app(config)

    def test_unreachable_storage_falls_back_to_local_limits(self, app):
        outage_app = self._app("redis://127.0.0.1:6/0")  # nothing listens on port 6
        _db.create_all()
        client = outage_app.test_client()

        statuses = [client.get("/login").status_code for _ in range(11)]

        assert statuses[:10] == [200] * 10
        assert statuses[10] == 429
        assert client.get("/healthz").get_json() == {"status": "degraded"}

    def test_memory_storage_reports_ok(self, client):
        assert client.get("/healthz").get_json() == {"status": "ok"}


def test_every_cdn_asset_has_subresource_integrity(app):
    import pathlib
    import re

    tag = re.compile(r"<(?:script|link)\b[^>]*https://cdn\.jsdelivr\.net[^>]*>", re.I | re.S)
    missing = []
    for path in pathlib.Path(app.template_folder).rglob("*.html"):
        for match in tag.finditer(path.read_text(encoding="utf-8")):
            if 'integrity="sha384-' not in match.group(0) or 'crossorigin="anonymous"' not in match.group(0):
                missing.append(path.name)
    assert missing == []


def test_notification_links_cannot_redirect_off_site(client, make_user, login_as):
    from gaminghub.models.notification import Notification

    user = make_user()
    n = Notification(user_id=user.id, type="achievement", title="x", link="https://evil.example/")
    _db.session.add(n)
    _db.session.commit()
    login_as(user)

    resp = client.get(f"/notifications/open/{n.id}")
    assert resp.headers["Location"] == "/notifications"


def test_favicon_redirects_to_the_real_icon(client):
    resp = client.get("/favicon.ico")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/static/images/favicon.png")
