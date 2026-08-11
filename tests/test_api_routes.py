from gaminghub.services import api_auth_service


class TestTokenIssuance:

    def test_valid_credentials_return_a_token(self, client, make_user):
        make_user(email="api@test.com", password="apipass123")

        resp = client.post("/api/auth/token", json={"email": "api@test.com", "password": "apipass123"})

        assert resp.status_code == 201
        assert "token" in resp.get_json()

    def test_wrong_password_returns_401(self, client, make_user):
        make_user(email="api2@test.com", password="apipass123")

        resp = client.post("/api/auth/token", json={"email": "api2@test.com", "password": "wrong"})

        assert resp.status_code == 401


class TestTokenAuthEnforcement:

    def test_no_authorization_header_is_401(self, client):
        resp = client.get("/api/me")
        assert resp.status_code == 401

    def test_malformed_scheme_is_401(self, client, make_user):
        user = make_user()
        token = api_auth_service.issue_token(user)

        resp = client.get("/api/me", headers={"Authorization": f"Token {token}"})

        assert resp.status_code == 401

    def test_valid_token_authenticates_as_that_user(self, client, make_user):
        user = make_user(username="apiuser")
        token = api_auth_service.issue_token(user)

        resp = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 200
        assert resp.get_json()["user"]["username"] == "apiuser"

    def test_a_revoked_token_stops_authenticating(self, client, make_user):
        user = make_user()
        token = api_auth_service.issue_token(user)
        headers = {"Authorization": f"Bearer {token}"}

        assert client.get("/api/me", headers=headers).status_code == 200

        client.delete("/api/auth/token", headers=headers)

        assert client.get("/api/me", headers=headers).status_code == 401

    def test_one_user_s_token_cannot_read_another_user_s_notifications(self, client, make_user):
        from gaminghub.services import notification_service

        victim = make_user(username="victim")
        attacker = make_user(username="attacker")
        notification_service.create(victim, "achievement", "victim's notification")

        attacker_token = api_auth_service.issue_token(attacker)
        resp = client.get("/api/me/notifications", headers={"Authorization": f"Bearer {attacker_token}"})

        titles = [n["title"] for n in resp.get_json()["notifications"]]
        assert "victim's notification" not in titles


class TestCsrfIsNotRequired:
    """The api blueprint is exempted from CSRFProtect in the app factory --
    confirmed here with CSRF actually turned back on, since the shared
    test config leaves it off for every other test."""

    def test_post_succeeds_with_csrf_enabled_and_no_csrf_token_sent(self, app, make_user):
        app.config["WTF_CSRF_ENABLED"] = True
        client = app.test_client()

        user = make_user()
        token = api_auth_service.issue_token(user)

        resp = client.post(
            "/api/me/notifications/read-all",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert resp.status_code == 200


class TestJsonErrorHandlers:

    def test_unmatched_api_path_is_a_json_404(self, client):
        resp = client.get("/api/this-does-not-exist")
        assert resp.status_code == 404
        assert resp.content_type.startswith("application/json")

    def test_a_normal_html_404_is_unaffected(self, client):
        resp = client.get("/this-does-not-exist-either")
        assert resp.status_code == 404
        assert not resp.content_type.startswith("application/json")
