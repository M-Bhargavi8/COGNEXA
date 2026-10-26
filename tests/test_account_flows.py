"""
End-to-end tests for account self-service: registration + email
verification, password reset, password change, profile and email edits,
and the login/logout/session rules around them.
"""

import re
from datetime import datetime, timedelta

import pytest

from gaminghub.database.database import db as _db
from gaminghub.models.account_token import AccountToken
from gaminghub.models.api_token import ApiToken
from gaminghub.models.audit_log import AuditLog
from gaminghub.models.user import User
from gaminghub.services import api_auth_service
from gaminghub.services.email_service import get_outbox


def _outbox(app):
    with app.app_context():
        return get_outbox()


def _link_from_last_email(app, path_prefix):
    body = _outbox(app)[-1]["body"]
    match = re.search(r"(https?://\S+" + re.escape(path_prefix) + r"(\S+))", body)
    assert match, body
    return match.group(1), match.group(2)


def _register(client, username="newplayer", email="new@test.com", password="longenough1"):
    return client.post("/register", data={
        "username": username, "email": email,
        "password": password, "confirm_password": password
    })


# ---------------------------------------------------------- registration

class TestRegistrationAndVerification:

    def test_registration_sends_a_verification_email_built_from_app_base_url(self, app, client):
        _register(client)

        mail = _outbox(app)[-1]
        assert mail["to"] == "new@test.com"
        link, _ = _link_from_last_email(app, "/verify-email/")
        assert link.startswith("http://localhost/verify-email/")

    def test_new_account_starts_unverified(self, app, client):
        _register(client)
        assert User.query.filter_by(username="newplayer").one().email_verified_at is None

    def test_link_ignores_a_spoofed_host_header(self, app, client):
        client.post("/register", data={
            "username": "hostcheck", "email": "host@test.com",
            "password": "longenough1", "confirm_password": "longenough1"
        }, headers={"Host": "evil.example"})

        body = _outbox(app)[-1]["body"]
        assert "evil.example" not in body
        assert "http://localhost/verify-email/" in body

    def test_verification_link_verifies_once(self, app, client):
        _register(client)
        _, token = _link_from_last_email(app, "/verify-email/")

        client.get(f"/verify-email/{token}")
        user = User.query.filter_by(username="newplayer").one()
        assert user.email_verified_at is not None

        resp = client.get(f"/verify-email/{token}", follow_redirects=True)
        assert b"invalid or has expired" in resp.data

    def test_expired_verification_link_is_rejected(self, app, client):
        _register(client)
        _, token = _link_from_last_email(app, "/verify-email/")

        AccountToken.query.update({"expires_at": datetime.utcnow() - timedelta(seconds=1)})
        _db.session.commit()

        client.get(f"/verify-email/{token}")
        assert User.query.filter_by(username="newplayer").one().email_verified_at is None

    def test_tokens_are_stored_hashed(self, app, client):
        _register(client)
        _, token = _link_from_last_email(app, "/verify-email/")

        row = AccountToken.query.one()
        assert row.token_hash != token
        assert token not in row.token_hash

    def test_unverified_user_cannot_log_in_when_verification_is_required(self, app, client, make_user):
        app.config["EMAIL_VERIFICATION_REQUIRED"] = True
        make_user(email="unverified@test.com", password="correctpass1")

        resp = client.post("/login", data={"email": "unverified@test.com", "password": "correctpass1"}, follow_redirects=True)

        assert b"verify your email" in resp.data
        assert client.get("/dashboard").status_code == 302

    def test_unverified_user_can_log_in_when_verification_is_optional(self, client, make_user):
        make_user(email="optional@test.com", password="correctpass1")

        resp = client.post("/login", data={"email": "optional@test.com", "password": "correctpass1"}, follow_redirects=True)

        assert b"Login Successful" in resp.data

    def test_resend_for_signed_out_user_gives_the_same_answer_for_unknown_addresses(self, app, client, make_user):
        make_user(email="known@test.com")
        known = client.post("/verify-email/resend", data={"email": "known@test.com"}, follow_redirects=True)
        unknown = client.post("/verify-email/resend", data={"email": "nobody@test.com"}, follow_redirects=True)

        assert b"If that account needs verifying" in known.data
        assert b"If that account needs verifying" in unknown.data
        assert len(_outbox(app)) == 1

    def test_username_with_disallowed_characters_is_rejected(self, client):
        _register(client, username="bad name!")
        assert User.query.count() == 0

    def test_username_uniqueness_ignores_case(self, client, make_user):
        make_user(username="Taken")
        _register(client, username="taken", email="other@test.com")
        assert User.query.count() == 1

    def test_email_is_stored_lowercase_and_unique_ignoring_case(self, client, make_user):
        _register(client, email="Mixed@Test.com")
        assert User.query.one().email == "mixed@test.com"

        _register(client, username="second", email="MIXED@test.com")
        assert User.query.count() == 1


# --------------------------------------------------------- long passwords

class TestPasswordLengthLimits:
    """bcrypt>=5 raises on passwords over 72 bytes; these used to 500."""

    def test_registration_with_an_over_long_password_is_rejected_not_a_500(self, client):
        resp = _register(client, password="a" * 80)
        assert resp.status_code == 302
        assert User.query.count() == 0

    def test_multibyte_password_over_72_bytes_is_rejected(self, client):
        resp = _register(client, password="é" * 40)  # 40 chars, 80 bytes
        assert resp.status_code == 302
        assert User.query.count() == 0

    def test_login_with_an_over_long_password_fails_cleanly(self, client, make_user):
        make_user(email="long@test.com", password="correctpass1")

        resp = client.post("/login", data={"email": "long@test.com", "password": "x" * 200}, follow_redirects=True)

        assert resp.status_code == 200
        assert b"Invalid Email or Password" in resp.data

    def test_api_token_with_an_over_long_password_is_a_401(self, client, make_user):
        make_user(email="longapi@test.com", password="correctpass1")
        resp = client.post("/api/auth/token", json={"email": "longapi@test.com", "password": "x" * 200})
        assert resp.status_code == 401


# --------------------------------------------------------- password reset

class TestPasswordReset:

    def _request_reset(self, client, email):
        return client.post("/forgot-password", data={"email": email}, follow_redirects=True)

    def test_response_is_identical_for_known_and_unknown_addresses(self, app, client, make_user):
        make_user(email="exists@test.com")

        known = self._request_reset(client, "exists@test.com")
        unknown = self._request_reset(client, "missing@test.com")

        message = b"If an account exists for that email"
        assert message in known.data and message in unknown.data
        assert len(_outbox(app)) == 1

    def test_full_reset_flow_changes_the_password_once(self, app, client, make_user):
        user = make_user(email="reset@test.com", password="oldpassword1")
        self._request_reset(client, "reset@test.com")
        link, token = _link_from_last_email(app, "/reset-password/")
        assert link.startswith("http://localhost/reset-password/")

        landing = client.get(f"/reset-password/{token}")
        assert landing.status_code == 302
        assert landing.headers["Location"].endswith("/reset-password")

        resp = client.post("/reset-password", data={"password": "brandnewpass1", "confirm_password": "brandnewpass1"})
        assert resp.status_code == 302

        login = client.post("/login", data={"email": "reset@test.com", "password": "brandnewpass1"}, follow_redirects=True)
        assert b"Login Successful" in login.data

        # The link can't be used a second time.
        client.post("/logout")
        again = client.get(f"/reset-password/{token}", follow_redirects=True)
        assert b"invalid or has expired" in again.data

        assert AuditLog.query.filter_by(action="password_reset", target_id=user.id).count() == 1

    def test_reset_marks_the_address_verified(self, app, client, make_user):
        make_user(email="verifyme@test.com", password="oldpassword1")
        self._request_reset(client, "verifyme@test.com")
        _, token = _link_from_last_email(app, "/reset-password/")

        client.get(f"/reset-password/{token}")
        client.post("/reset-password", data={"password": "brandnewpass1", "confirm_password": "brandnewpass1"})

        assert User.query.filter_by(email="verifyme@test.com").one().email_verified_at is not None

    def test_expired_reset_token_is_rejected(self, app, client, make_user):
        make_user(email="expired@test.com", password="oldpassword1")
        self._request_reset(client, "expired@test.com")
        _, token = _link_from_last_email(app, "/reset-password/")

        AccountToken.query.update({"expires_at": datetime.utcnow() - timedelta(seconds=1)})
        _db.session.commit()

        resp = client.get(f"/reset-password/{token}", follow_redirects=True)
        assert b"invalid or has expired" in resp.data

    def test_a_newer_reset_request_retires_the_older_link(self, app, client, make_user):
        make_user(email="twice@test.com", password="oldpassword1")
        self._request_reset(client, "twice@test.com")
        _, first = _link_from_last_email(app, "/reset-password/")

        AccountToken.query.update({"created_at": datetime.utcnow() - timedelta(minutes=10)})
        _db.session.commit()

        self._request_reset(client, "twice@test.com")
        _, second = _link_from_last_email(app, "/reset-password/")

        assert first != second
        assert client.get(f"/reset-password/{first}").headers["Location"].endswith("/forgot-password")
        assert client.get(f"/reset-password/{second}").headers["Location"].endswith("/reset-password")

    def test_repeat_requests_within_the_cooldown_send_one_email(self, app, client, make_user):
        make_user(email="flood@test.com")
        for _ in range(3):
            self._request_reset(client, "flood@test.com")
        assert len(_outbox(app)) == 1

    def test_reset_signs_out_existing_sessions_and_revokes_api_tokens(self, app, client, make_user, login_as):
        user = make_user(email="signout@test.com", password="oldpassword1")
        api_auth_service.issue_token(user)
        login_as(user)
        assert client.get("/dashboard").status_code == 200

        other = app.test_client()
        other.post("/forgot-password", data={"email": "signout@test.com"})
        _, token = _link_from_last_email(app, "/reset-password/")
        other.get(f"/reset-password/{token}")
        other.post("/reset-password", data={"password": "brandnewpass1", "confirm_password": "brandnewpass1"})

        assert client.get("/dashboard").status_code == 302
        assert ApiToken.query.filter_by(user_id=user.id).count() == 0

    def test_mismatched_passwords_do_not_consume_the_token(self, app, client, make_user):
        make_user(email="mismatch@test.com", password="oldpassword1")
        self._request_reset(client, "mismatch@test.com")
        _, token = _link_from_last_email(app, "/reset-password/")

        client.get(f"/reset-password/{token}")
        client.post("/reset-password", data={"password": "brandnewpass1", "confirm_password": "different123"})

        assert AccountToken.query.one().used_at is None

    def test_reset_page_without_a_token_redirects(self, client):
        assert client.get("/reset-password").headers["Location"].endswith("/forgot-password")

    def test_suspended_accounts_get_no_reset_email(self, app, client, make_user):
        make_user(email="suspended@test.com", status="suspended")
        self._request_reset(client, "suspended@test.com")
        assert _outbox(app) == []


# -------------------------------------------------------- password change

class TestPasswordChange:

    def test_requires_the_current_password(self, client, make_user, login_as):
        user = make_user(password="currentpass1")
        login_as(user)

        resp = client.post("/account/password", data={
            "current_password": "wrongpass1", "new_password": "newpassword1", "confirm_password": "newpassword1"
        }, follow_redirects=True)

        assert b"current password is incorrect" in resp.data

    def test_change_keeps_this_session_but_signs_out_others(self, app, client, make_user, login_as):
        user = make_user(email="change@test.com", password="currentpass1")
        login_as(user)

        other = app.test_client()
        other.post("/login", data={"email": "change@test.com", "password": "currentpass1"})
        assert other.get("/dashboard").status_code == 200

        resp = client.post("/account/password", data={
            "current_password": "currentpass1", "new_password": "newpassword1", "confirm_password": "newpassword1"
        }, follow_redirects=True)

        assert b"Password updated" in resp.data
        assert client.get("/dashboard").status_code == 200
        assert other.get("/dashboard").status_code == 302

        assert _outbox(app)[-1]["subject"] == "Your COGNEXA password was changed"

    def test_new_password_must_differ(self, client, make_user, login_as):
        user = make_user(password="currentpass1")
        login_as(user)

        resp = client.post("/account/password", data={
            "current_password": "currentpass1", "new_password": "currentpass1", "confirm_password": "currentpass1"
        }, follow_redirects=True)

        assert b"different from your current one" in resp.data


# ---------------------------------------------------------------- profile

class TestProfileEdit:

    def test_settings_page_renders(self, client, make_user, login_as):
        login_as(make_user())
        resp = client.get("/account/")
        assert resp.status_code == 200
        assert b"Account settings" in resp.data

    def test_settings_requires_login(self, client):
        assert client.get("/account/").status_code == 302

    def test_updates_allowed_fields(self, client, make_user, make_game, login_as):
        make_game(name="Memory Matrix", slug="memory-matrix")
        user = make_user(username="before")
        login_as(user)

        client.post("/account/profile", data={
            "username": "after", "bio": "New bio", "country": "Canada", "favorite_game": "Memory Matrix"
        })

        user = _db.session.get(User, user.id)
        assert (user.username, user.bio, user.country, user.favorite_game) == ("after", "New bio", "Canada", "Memory Matrix")
        assert AuditLog.query.filter_by(action="username_changed").count() == 1

    def test_protected_fields_in_the_request_are_ignored(self, client, make_user, login_as):
        user = make_user(username="honest", coins=100)
        login_as(user)

        client.post("/account/profile", data={
            "username": "honest", "bio": "", "country": "", "favorite_game": "",
            "role": "admin", "coins": "999999", "xp": "999999", "status": "active", "email_verified_at": "2020-01-01"
        })

        user = _db.session.get(User, user.id)
        assert user.role == "player"
        assert user.coins == 100
        assert user.xp == 0
        assert user.email_verified_at is None

    def test_rejects_a_taken_username(self, client, make_user, login_as):
        make_user(username="occupied")
        user = make_user(username="mine")
        login_as(user)

        resp = client.post("/account/profile", data={"username": "Occupied", "bio": "", "country": "", "favorite_game": ""}, follow_redirects=True)

        assert b"Username already exists" in resp.data
        assert _db.session.get(User, user.id).username == "mine"

    def test_rejects_an_unknown_favorite_game(self, client, make_user, login_as):
        user = make_user()
        login_as(user)

        resp = client.post("/account/profile", data={"username": user.username, "bio": "", "country": "", "favorite_game": "Not A Game"}, follow_redirects=True)

        assert b"Pick a favorite game" in resp.data

    def test_rejects_an_over_long_bio(self, client, make_user, login_as):
        user = make_user()
        login_as(user)

        resp = client.post("/account/profile", data={"username": user.username, "bio": "x" * 301, "country": "", "favorite_game": ""}, follow_redirects=True)

        assert b"Bio must be at most" in resp.data

    def test_profile_page_links_to_settings(self, client, make_user, login_as):
        login_as(make_user())
        assert b'href="/account/"' in client.get("/profile").data


# ------------------------------------------------------------ email change

class TestEmailChange:

    def test_email_changes_only_after_the_new_address_is_confirmed(self, app, client, make_user, login_as):
        user = make_user(email="old@test.com", password="currentpass1")
        login_as(user)

        client.post("/account/email", data={"email": "New@Test.com", "current_password": "currentpass1"})

        assert _db.session.get(User, user.id).email == "old@test.com"
        assert _outbox(app)[-1]["to"] == "new@test.com"
        assert b"new@test.com" in client.get("/account/").data  # pending notice

        _, token = _link_from_last_email(app, "/verify-email/")
        client.get(f"/verify-email/{token}")

        user = _db.session.get(User, user.id)
        assert user.email == "new@test.com"
        assert user.email_verified_at is not None
        assert _outbox(app)[-1]["to"] == "old@test.com"  # heads-up to the old address

    def test_requires_the_current_password(self, app, client, make_user, login_as):
        login_as(make_user(password="currentpass1"))

        resp = client.post("/account/email", data={"email": "x@test.com", "current_password": "nope"}, follow_redirects=True)

        assert b"current password is incorrect" in resp.data
        assert _outbox(app) == []

    def test_cannot_take_an_address_registered_in_the_meantime(self, app, client, make_user, login_as):
        user = make_user(email="first@test.com", password="currentpass1")
        login_as(user)
        client.post("/account/email", data={"email": "contested@test.com", "current_password": "currentpass1"})
        _, token = _link_from_last_email(app, "/verify-email/")

        make_user(username="squatter", email="contested@test.com")
        client.get(f"/verify-email/{token}")

        assert _db.session.get(User, user.id).email == "first@test.com"


# ------------------------------------------------------- login and logout

class TestLoginRedirects:

    @pytest.mark.parametrize("target", ["/analytics", "/leaderboard?period=daily"])
    def test_safe_next_is_followed(self, client, make_user, target):
        make_user(email="next@test.com", password="correctpass1")

        resp = client.post(f"/login?next={target}", data={"email": "next@test.com", "password": "correctpass1"})

        assert resp.headers["Location"] == target

    @pytest.mark.parametrize("target", [
        "https://evil.example/", "//evil.example/", "/\\evil.example", "javascript:alert(1)", "\\\\evil.example"
    ])
    def test_unsafe_next_is_ignored(self, client, make_user, target):
        make_user(email="next2@test.com", password="correctpass1")

        resp = client.post("/login", query_string={"next": target}, data={"email": "next2@test.com", "password": "correctpass1"})

        assert resp.headers["Location"] == "/dashboard"

    def test_login_required_redirect_round_trips(self, client, make_user):
        make_user(email="round@test.com", password="correctpass1")

        bounce = client.get("/analytics")
        assert "/login?next=" in bounce.headers["Location"]

        resp = client.post(bounce.headers["Location"], data={"email": "round@test.com", "password": "correctpass1"})
        assert resp.headers["Location"] == "/analytics"

    def test_remember_me_sets_a_persistent_cookie(self, client, make_user):
        make_user(email="remember@test.com", password="correctpass1")

        resp = client.post("/login", data={"email": "remember@test.com", "password": "correctpass1", "remember": "1"})

        cookies = resp.headers.getlist("Set-Cookie")
        remember = [c for c in cookies if c.startswith("remember_token=")]
        assert remember and "HttpOnly" in remember[0]

    def test_without_remember_me_there_is_no_persistent_cookie(self, client, make_user):
        make_user(email="noremember@test.com", password="correctpass1")

        resp = client.post("/login", data={"email": "noremember@test.com", "password": "correctpass1"})

        assert not any(c.startswith("remember_token=") for c in resp.headers.getlist("Set-Cookie"))

    def test_login_records_last_login(self, client, make_user):
        user = make_user(email="lastlogin@test.com", password="correctpass1")
        client.post("/login", data={"email": "lastlogin@test.com", "password": "correctpass1"})
        assert _db.session.get(User, user.id).last_login is not None

    def test_email_lookup_ignores_case(self, client, make_user):
        make_user(email="case@test.com", password="correctpass1")
        resp = client.post("/login", data={"email": "CASE@Test.com", "password": "correctpass1"}, follow_redirects=True)
        assert b"Login Successful" in resp.data

    def test_suspended_user_cannot_log_in(self, client, make_user):
        make_user(email="banned@test.com", password="correctpass1", status="suspended")
        resp = client.post("/login", data={"email": "banned@test.com", "password": "correctpass1"}, follow_redirects=True)
        assert b"not active" in resp.data


class TestLogoutAndSessions:

    def test_logout_rejects_get(self, client, make_user, login_as):
        login_as(make_user())

        assert client.get("/logout").status_code == 405
        assert client.get("/dashboard").status_code == 200

    def test_logout_post_signs_out(self, client, make_user, login_as):
        login_as(make_user())
        client.post("/logout")
        assert client.get("/dashboard").status_code == 302

    def test_legacy_session_without_version_still_works_until_version_changes(self, client, make_user, login_as):
        user = make_user()
        login_as(user)  # writes the old bare "<id>" format
        assert client.get("/dashboard").status_code == 200

        user.auth_version = 1
        _db.session.commit()
        assert client.get("/dashboard").status_code == 302

    def test_session_for_a_suspended_user_stops_working(self, client, make_user, login_as):
        user = make_user()
        login_as(user)
        user.status = "suspended"
        _db.session.commit()

        assert client.get("/dashboard").status_code == 302

    def test_garbage_session_id_is_treated_as_signed_out(self, client):
        with client.session_transaction() as sess:
            sess["_user_id"] = "not-a-number:x"
        assert client.get("/dashboard").status_code == 302


class TestDailyClaimIsPostOnly:

    def test_get_is_rejected(self, client, make_user, login_as):
        login_as(make_user())
        assert client.get("/daily").status_code == 405

    def test_post_claims(self, client, make_user, login_as):
        user = make_user(coins=0)
        login_as(user)
        client.post("/daily")
        assert _db.session.get(User, user.id).coins == 20


class TestLegacyCaseVariantEmails:
    """Accounts created before emails were normalised can differ only by
    case. Each must still be reachable, and nothing may guess between them."""

    def test_each_case_variant_logs_into_its_own_account(self, client, make_user):
        make_user(username="lower", email="dup@test.com", password="lowerpass1")
        make_user(username="upper", email="Dup@test.com", password="upperpass1")

        resp = client.post("/login", data={"email": "Dup@test.com", "password": "upperpass1"}, follow_redirects=True)
        assert b"Login Successful" in resp.data
        client.post("/logout")

        resp = client.post("/login", data={"email": "dup@test.com", "password": "lowerpass1"}, follow_redirects=True)
        assert b"Login Successful" in resp.data

    def test_ambiguous_reset_request_sends_nothing(self, app, client, make_user):
        make_user(username="lower", email="dup@test.com")
        make_user(username="upper", email="Dup@test.com")

        client.post("/forgot-password", data={"email": "DUP@TEST.COM"})

        assert _outbox(app) == []
