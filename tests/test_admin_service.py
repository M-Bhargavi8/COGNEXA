from gaminghub.services import admin_service


class TestGetOverviewStats:

    def test_reports_correct_totals(self, make_user):
        make_user(username="a", role="player")
        make_user(username="b", role="admin")

        stats = admin_service.get_overview_stats()

        assert stats["total_users"] == 2
        assert stats["total_admins"] == 1
        assert stats["total_games_played"] == 0
        assert stats["most_played_game"] is None


class TestSearchUsers:

    def test_no_query_returns_everyone(self, make_user):
        make_user(username="alice")
        make_user(username="bob")
        assert len(admin_service.search_users(None)) == 2

    def test_query_filters_by_substring_case_insensitively(self, make_user):
        make_user(username="Alice")
        make_user(username="bob")

        results = admin_service.search_users("ali")

        assert [u.username for u in results] == ["Alice"]


class TestSetUserRole:

    def test_promotes_a_different_user_to_admin(self, make_user):
        admin = make_user(username="admin1", role="admin")
        player = make_user(username="player1", role="player")

        success, message = admin_service.set_user_role(admin, player, "admin")

        assert success is True
        assert player.role == "admin"

    def test_demotes_a_different_user_to_player(self, make_user):
        actor = make_user(username="actor", role="admin")
        target = make_user(username="target", role="admin")

        success, message = admin_service.set_user_role(actor, target, "player")

        assert success is True
        assert target.role == "player"

    def test_an_admin_cannot_change_their_own_role(self, make_user):
        admin = make_user(username="admin1", role="admin")

        success, message = admin_service.set_user_role(admin, admin, "player")

        assert success is False
        assert admin.role == "admin"

    def test_rejects_an_invalid_role_string(self, make_user):
        admin = make_user(username="admin1", role="admin")
        player = make_user(username="player1", role="player")

        success, message = admin_service.set_user_role(admin, player, "superuser")

        assert success is False
        assert player.role == "player"


class TestToggles:

    def test_toggle_game_active_flips_and_returns_new_state(self, make_game):
        game = make_game(is_active=True)

        first = admin_service.toggle_game_active(game)
        assert first is False
        assert game.is_active is False

        second = admin_service.toggle_game_active(game)
        assert second is True

    def test_toggle_shop_item_active_flips_and_returns_new_state(self, make_shop_item):
        item = make_shop_item(is_active=True)

        result = admin_service.toggle_shop_item_active(item)

        assert result is False
        assert item.is_active is False
