from gaminghub.database.database import db as _db


ADMIN_PATHS = ["/admin/", "/admin/users", "/admin/games", "/admin/shop"]


class TestAccessControl:

    def test_anonymous_user_is_redirected_to_login(self, client):
        for path in ADMIN_PATHS:
            resp = client.get(path, follow_redirects=False)
            assert resp.status_code == 302, path

    def test_logged_in_player_gets_403(self, client, make_user, login_as):
        player = make_user(role="player")
        login_as(player)

        for path in ADMIN_PATHS:
            resp = client.get(path)
            assert resp.status_code == 403, path

    def test_logged_in_admin_can_access_everything(self, client, make_user, login_as):
        admin = make_user(role="admin")
        login_as(admin)

        for path in ADMIN_PATHS:
            resp = client.get(path)
            assert resp.status_code == 200, path


class TestUserRoleToggleRoute:

    def test_promotes_a_different_user_through_the_route(self, client, make_user, login_as, db):
        from gaminghub.models.user import User

        admin = make_user(username="admin1", role="admin")
        player = make_user(username="player1", role="player")
        login_as(admin)

        resp = client.post(f"/admin/users/{player.id}/role", follow_redirects=True)

        assert resp.status_code == 200
        assert _db.session.get(User, player.id).role == "admin"

    def test_cannot_change_own_role_through_the_route(self, client, make_user, login_as):
        admin = make_user(username="admin1", role="admin")
        login_as(admin)

        client.post(f"/admin/users/{admin.id}/role", follow_redirects=True)

        assert admin.role == "admin"

    def test_toggling_a_nonexistent_user_404s(self, client, make_user, login_as):
        admin = make_user(role="admin")
        login_as(admin)

        resp = client.post("/admin/users/999999/role")

        assert resp.status_code == 404


class TestGameAndShopToggleRoutes:

    def test_toggling_a_game_flips_is_active(self, client, make_user, make_game, login_as, db):
        from gaminghub.models.game import Game

        admin = make_user(role="admin")
        game = make_game(is_active=True)
        login_as(admin)

        client.post(f"/admin/games/{game.id}/toggle")

        assert _db.session.get(Game, game.id).is_active is False

    def test_toggling_a_shop_item_flips_is_active(self, client, make_user, make_shop_item, login_as, db):
        from gaminghub.models.shop_item import ShopItem

        admin = make_user(role="admin")
        item = make_shop_item(is_active=True)
        login_as(admin)

        client.post(f"/admin/shop/{item.id}/toggle")

        assert _db.session.get(ShopItem, item.id).is_active is False

    def test_a_deactivated_game_disappears_from_the_brain_lab_hub(self, client, make_user, make_game, login_as):
        admin = make_user(role="admin")
        game = make_game(slug="memory-matrix", category="brain-lab", name="Memory Matrix", is_active=True)
        login_as(admin)

        resp_before = client.get("/brain-lab/")
        assert b"No Brain Lab games available" not in resp_before.data

        client.post(f"/admin/games/{game.id}/toggle")

        # a fresh, unrelated request avoids the deactivate flash message
        # itself containing "Memory Matrix" ("Memory Matrix is now
        # inactive."), which would otherwise poison a substring check
        client.get("/dashboard")
        resp_after = client.get("/brain-lab/")
        assert b"No Brain Lab games available" in resp_after.data
