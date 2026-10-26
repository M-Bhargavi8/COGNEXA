from gaminghub.models.user import User


class TestRegisterValidation:

    def test_username_too_short_is_rejected(self, client, db):
        resp = client.post("/register", data={
            "username": "ab", "email": "a@test.com",
            "password": "longenough1", "confirm_password": "longenough1"
        }, follow_redirects=False)

        assert resp.status_code == 302
        assert User.query.filter_by(email="a@test.com").first() is None

    def test_malformed_email_is_rejected(self, client, db):
        resp = client.post("/register", data={
            "username": "gooduser", "email": "not-an-email",
            "password": "longenough1", "confirm_password": "longenough1"
        })

        assert User.query.filter_by(username="gooduser").first() is None

    def test_short_password_is_rejected(self, client, db):
        client.post("/register", data={
            "username": "gooduser2", "email": "b@test.com",
            "password": "short1", "confirm_password": "short1"
        })

        assert User.query.filter_by(username="gooduser2").first() is None

    def test_mismatched_passwords_rejected(self, client, db):
        client.post("/register", data={
            "username": "gooduser3", "email": "c@test.com",
            "password": "longenough1", "confirm_password": "different1"
        })

        assert User.query.filter_by(username="gooduser3").first() is None

    def test_valid_registration_creates_a_user_with_a_hashed_password(self, client, db):
        resp = client.post("/register", data={
            "username": "realuser", "email": "real@test.com",
            "password": "longenough1", "confirm_password": "longenough1"
        }, follow_redirects=True)

        assert resp.status_code == 200
        user = User.query.filter_by(username="realuser").first()
        assert user is not None
        assert user.password != "longenough1"  # never stored in plaintext

    def test_duplicate_username_rejected(self, client, make_user, db):
        make_user(username="taken")

        client.post("/register", data={
            "username": "taken", "email": "different@test.com",
            "password": "longenough1", "confirm_password": "longenough1"
        })

        assert User.query.filter_by(email="different@test.com").first() is None

    def test_duplicate_email_rejected(self, client, make_user, db):
        make_user(username="original", email="dupe@test.com")

        client.post("/register", data={
            "username": "different", "email": "dupe@test.com",
            "password": "longenough1", "confirm_password": "longenough1"
        })

        assert User.query.filter_by(username="different").first() is None

    def test_username_and_email_are_stripped_of_surrounding_whitespace(self, client, db):
        client.post("/register", data={
            "username": "  spacedname  ", "email": "  spaced@test.com  ",
            "password": "longenough1", "confirm_password": "longenough1"
        })

        assert User.query.filter_by(username="spacedname").first() is not None


class TestLogin:

    def test_correct_credentials_logs_in(self, client, make_user):
        make_user(email="login@test.com", password="correctpass1")

        resp = client.post("/login", data={"email": "login@test.com", "password": "correctpass1"}, follow_redirects=True)

        assert resp.status_code == 200
        assert b"Login Successful" in resp.data

    def test_wrong_password_is_rejected(self, client, make_user):
        make_user(email="login2@test.com", password="correctpass1")

        resp = client.post("/login", data={"email": "login2@test.com", "password": "wrongpass"}, follow_redirects=True)

        assert b"Invalid Email or Password" in resp.data

    def test_unknown_email_is_rejected(self, client):
        resp = client.post("/login", data={"email": "nobody@test.com", "password": "whatever1"}, follow_redirects=True)
        assert b"Invalid Email or Password" in resp.data

    def test_login_required_route_redirects_when_not_authenticated(self, client):
        resp = client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 302

    def test_logout_clears_the_session(self, client, make_user, login_as):
        user = make_user()
        login_as(user)

        client.post("/logout")
        resp = client.get("/dashboard", follow_redirects=False)

        assert resp.status_code == 302


class TestRateLimiting:
    """Uses the separate rate_limited_app/client fixtures -- the default
    ones leave RATELIMIT_ENABLED off so the rest of the suite isn't
    tripping over request budgets it has no reason to care about."""

    def test_login_is_rate_limited_after_ten_requests_per_minute(self, rate_limited_client):
        statuses = [rate_limited_client.get("/login").status_code for _ in range(14)]
        assert statuses[:10] == [200] * 10
        assert all(s == 429 for s in statuses[10:])

    def test_register_is_rate_limited_after_five_requests_per_hour(self, rate_limited_client):
        statuses = [rate_limited_client.get("/register").status_code for _ in range(8)]
        assert statuses[:5] == [200] * 5
        assert all(s == 429 for s in statuses[5:])
