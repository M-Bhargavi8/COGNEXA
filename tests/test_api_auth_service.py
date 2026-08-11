from gaminghub.services import api_auth_service
from gaminghub.models.api_token import ApiToken


class TestIssueToken:

    def test_returns_a_high_entropy_raw_token(self, make_user):
        user = make_user()
        token = api_auth_service.issue_token(user)

        assert isinstance(token, str)
        assert len(token) == 64  # secrets.token_hex(32)

    def test_only_the_hash_is_stored_not_the_raw_token(self, make_user):
        user = make_user()
        token = api_auth_service.issue_token(user)

        row = ApiToken.query.filter_by(user_id=user.id).first()

        assert row.token_hash != token
        assert len(row.token_hash) == 64  # sha256 hex digest

    def test_issuing_twice_creates_two_independent_tokens(self, make_user):
        user = make_user()
        token1 = api_auth_service.issue_token(user)
        token2 = api_auth_service.issue_token(user)

        assert token1 != token2
        assert ApiToken.query.filter_by(user_id=user.id).count() == 2


class TestGetUserForToken:

    def test_resolves_a_valid_token_to_its_user(self, make_user):
        user = make_user()
        token = api_auth_service.issue_token(user)

        resolved = api_auth_service.get_user_for_token(token)

        assert resolved.id == user.id

    def test_garbage_token_resolves_to_none(self, app):
        assert api_auth_service.get_user_for_token("not-a-real-token") is None

    def test_empty_or_none_token_resolves_to_none(self, app):
        assert api_auth_service.get_user_for_token("") is None
        assert api_auth_service.get_user_for_token(None) is None

    def test_updates_last_used_at(self, make_user):
        user = make_user()
        token = api_auth_service.issue_token(user)
        row = ApiToken.query.filter_by(user_id=user.id).first()
        assert row.last_used_at is None

        api_auth_service.get_user_for_token(token)

        assert row.last_used_at is not None


class TestRevokeToken:

    def test_revoking_a_valid_token_removes_it(self, make_user):
        user = make_user()
        token = api_auth_service.issue_token(user)

        revoked = api_auth_service.revoke_token(token)

        assert revoked is True
        assert ApiToken.query.filter_by(user_id=user.id).count() == 0

    def test_a_revoked_token_no_longer_resolves_to_a_user(self, make_user):
        user = make_user()
        token = api_auth_service.issue_token(user)
        api_auth_service.revoke_token(token)

        assert api_auth_service.get_user_for_token(token) is None

    def test_revoking_a_nonexistent_token_returns_false(self, app):
        assert api_auth_service.revoke_token("not-a-real-token") is False

    def test_revoking_one_token_does_not_affect_a_second_token_for_the_same_user(self, make_user):
        user = make_user()
        token1 = api_auth_service.issue_token(user)
        token2 = api_auth_service.issue_token(user)

        api_auth_service.revoke_token(token1)

        assert api_auth_service.get_user_for_token(token1) is None
        assert api_auth_service.get_user_for_token(token2) is not None
