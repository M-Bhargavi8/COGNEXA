"""
Admin user/game/shop management and the audit trail: permissions,
validation, last-admin protection and what each action records.
"""

import json

import pytest

from gaminghub.database.database import db as _db
from gaminghub.models.api_token import ApiToken
from gaminghub.models.audit_log import AuditLog
from gaminghub.models.game import Game
from gaminghub.models.shop_item import ShopItem
from gaminghub.models.user import User
from gaminghub.services import admin_service, api_auth_service, leaderboard_service


NEW_ADMIN_ROUTES = [
    ("GET", "/admin/users/{uid}"),
    ("POST", "/admin/users/{uid}/status"),
    ("POST", "/admin/users/{uid}/adjust"),
    ("GET", "/admin/games/new"),
    ("GET", "/admin/games/{gid}/edit"),
    ("POST", "/admin/games/{gid}/edit"),
    ("GET", "/admin/shop/new"),
    ("POST", "/admin/shop/new"),
    ("GET", "/admin/shop/{sid}/edit"),
    ("POST", "/admin/shop/{sid}/edit"),
    ("GET", "/admin/audit"),
]


@pytest.fixture
def admin_user(make_user):
    return make_user(username="boss", role="admin")


@pytest.fixture
def as_admin(client, admin_user, login_as):
    login_as(admin_user)
    return client


class TestPermissions:

    def _paths(self, user, game, item):
        return [(m, p.format(uid=user.id, gid=game.id, sid=item.id)) for m, p in NEW_ADMIN_ROUTES]

    def test_players_get_403_everywhere(self, client, make_user, make_game, make_shop_item, login_as):
        player = make_user(username="pleb")
        game, item = make_game(), make_shop_item()
        login_as(player)

        for method, path in self._paths(player, game, item):
            resp = client.open(path, method=method, data={"status": "suspended", "reason": "x", "coins": "5"})
            assert resp.status_code == 403, (method, path)

        assert _db.session.get(User, player.id).coins == 100

    def test_anonymous_is_sent_to_login(self, client, make_user, make_game, make_shop_item):
        user, game, item = make_user(), make_game(), make_shop_item()
        for method, path in self._paths(user, game, item):
            assert client.open(path, method=method).status_code == 302, (method, path)

    def test_admin_can_open_every_page(self, as_admin, admin_user, make_user, make_game, make_shop_item):
        user, game, item = make_user(username="someone"), make_game(), make_shop_item()
        for method, path in self._paths(user, game, item):
            if method == "GET" and path != "/admin/games/new":
                assert as_admin.get(path).status_code == 200, path

    def test_admin_post_without_csrf_token_is_rejected(self, make_user):
        """The default test config disables CSRF; this builds an app with it on."""
        import os
        import tempfile
        import uuid
        from gaminghub import create_app
        from tests.conftest import _make_test_config

        db_path = os.path.join(tempfile.gettempdir(), f"gaminghub_csrf_{uuid.uuid4().hex}.sqlite")
        config = _make_test_config(db_path)
        config.WTF_CSRF_ENABLED = True
        csrf_app = create_app(config)

        with csrf_app.app_context():
            _db.create_all()
            boss = User(username="csrfboss", email="c@test.com", password="x", role="admin")
            victim = User(username="victim", email="v@test.com", password="x")
            _db.session.add_all([boss, victim])
            _db.session.commit()

            client = csrf_app.test_client()
            with client.session_transaction() as sess:
                sess["_user_id"] = str(boss.id)

            resp = client.post(f"/admin/users/{victim.id}/status", data={"status": "suspended", "reason": "nope"})
            assert resp.status_code == 400
            assert _db.session.get(User, victim.id).status == "active"

            resp = client.post("/logout")
            assert resp.status_code == 400

            _db.session.remove()
            _db.engine.dispose()

        if os.path.exists(db_path):
            os.remove(db_path)


class TestUserStatus:

    def test_suspend_requires_a_reason(self, as_admin, admin_user, make_user):
        target = make_user(username="target")
        as_admin.post(f"/admin/users/{target.id}/status", data={"status": "suspended", "reason": ""})
        assert _db.session.get(User, target.id).status == "active"

    def test_suspend_signs_out_revokes_tokens_and_audits(self, app, as_admin, admin_user, make_user):
        target = make_user(username="target")
        api_auth_service.issue_token(target)

        victim_client = app.test_client()
        with victim_client.session_transaction() as sess:
            sess["_user_id"] = target.get_id()
        assert victim_client.get("/dashboard").status_code == 200

        as_admin.post(f"/admin/users/{target.id}/status", data={"status": "suspended", "reason": "Cheating"})

        target = _db.session.get(User, target.id)
        assert target.status == "suspended"
        assert target.status_reason == "Cheating"
        assert ApiToken.query.filter_by(user_id=target.id).count() == 0
        assert victim_client.get("/dashboard").status_code == 302

        entry = AuditLog.query.filter_by(action="user_status_changed").one()
        assert (entry.actor_id, entry.target_id, entry.reason) == (admin_user.id, target.id, "Cheating")
        assert json.loads(entry.details) == {"from": "active", "to": "suspended"}

    def test_reactivation_restores_login(self, client, as_admin, make_user):
        target = make_user(username="comeback", email="cb@test.com", password="correctpass1", status="suspended")
        as_admin.post(f"/admin/users/{target.id}/status", data={"status": "active", "reason": ""})
        assert _db.session.get(User, target.id).status == "active"

    def test_admin_cannot_change_own_status(self, as_admin, admin_user):
        as_admin.post(f"/admin/users/{admin_user.id}/status", data={"status": "suspended", "reason": "oops"})
        assert _db.session.get(User, admin_user.id).status == "active"

    def test_invalid_status_is_rejected(self, as_admin, make_user):
        target = make_user(username="target")
        as_admin.post(f"/admin/users/{target.id}/status", data={"status": "superuser", "reason": "x"})
        assert _db.session.get(User, target.id).status == "active"

    def test_suspended_users_are_hidden_from_leaderboards(self, make_user):
        visible = make_user(username="visible", level=5)
        hidden = make_user(username="hidden", level=9, status="suspended")

        board = leaderboard_service.get_global_leaderboard()
        names = [e["user"].username for e in board]

        assert "visible" in names and "hidden" not in names
        assert leaderboard_service.get_my_global_rank(visible) == 1

    def test_unknown_user_is_404(self, as_admin):
        assert as_admin.get("/admin/users/99999").status_code == 404


class TestLastAdminProtection:

    def test_cannot_demote_or_suspend_the_last_active_admin(self, make_user):
        acting = make_user(username="acting", role="admin", status="suspended")
        last = make_user(username="last", role="admin")

        ok, message = admin_service.set_user_role(acting, last, "player")
        assert not ok and "last active administrator" in message

        ok, message = admin_service.set_user_status(acting, last, "suspended", "because")
        assert not ok and "last active administrator" in message

    def test_can_demote_an_admin_when_another_remains(self, make_user):
        a = make_user(username="a1", role="admin")
        b = make_user(username="a2", role="admin")

        ok, _ = admin_service.set_user_role(a, b, "player")
        assert ok
        assert AuditLog.query.filter_by(action="user_role_changed").count() == 1

    def test_cannot_promote_a_suspended_account(self, make_user):
        a = make_user(username="a1", role="admin")
        b = make_user(username="b1", status="suspended")

        ok, _ = admin_service.set_user_role(a, b, "admin")
        assert not ok


class TestBalanceAdjustment:

    def test_coin_adjustment_is_applied_and_audited(self, as_admin, admin_user, make_user):
        target = make_user(username="target", coins=100)

        as_admin.post(f"/admin/users/{target.id}/adjust", data={"coins": "-40", "xp": "", "reason": "Refund reversal"})

        assert _db.session.get(User, target.id).coins == 60
        entry = AuditLog.query.filter_by(action="user_balance_adjusted").one()
        details = json.loads(entry.details)
        assert (details["coins_before"], details["coins_after"], details["coins_delta"]) == (100, 60, -40)
        assert entry.reason == "Refund reversal"

    def test_balance_cannot_go_negative(self, as_admin, make_user):
        target = make_user(username="target", coins=10)
        as_admin.post(f"/admin/users/{target.id}/adjust", data={"coins": "-11", "reason": "Too much"})
        assert _db.session.get(User, target.id).coins == 10

    def test_xp_grant_levels_up(self, as_admin, make_user):
        target = make_user(username="target")
        as_admin.post(f"/admin/users/{target.id}/adjust", data={"xp": "150", "reason": "Event prize"})

        target = _db.session.get(User, target.id)
        assert (target.level, target.xp) == (2, 50)

    @pytest.mark.parametrize("coins,xp,reason", [
        ("", "-5", "Remove xp"),          # XP can't be removed
        ("abc", "", "Bad number"),        # not an integer
        ("1000001", "", "Way too much"),  # over the bound
        ("5", "", ""),                    # reason required
        ("", "", "Nothing"),              # nothing to adjust
    ])
    def test_invalid_adjustments_change_nothing(self, as_admin, make_user, coins, xp, reason):
        target = make_user(username="target", coins=100)
        as_admin.post(f"/admin/users/{target.id}/adjust", data={"coins": coins, "xp": xp, "reason": reason})

        target = _db.session.get(User, target.id)
        assert (target.coins, target.xp, target.level) == (100, 0, 1)
        assert AuditLog.query.count() == 0


class TestGameManagement:

    def test_edit_changes_name_and_description_only(self, as_admin, make_game):
        game = make_game(name="Old", slug="memory-matrix", category="brain-lab")

        as_admin.post(f"/admin/games/{game.id}/edit", data={
            "name": "New Name", "description": "New desc", "slug": "hacked", "category": "classic-arcade"
        })

        game = _db.session.get(Game, game.id)
        assert (game.name, game.description, game.slug, game.category) == ("New Name", "New desc", "memory-matrix", "brain-lab")
        assert AuditLog.query.filter_by(action="game_updated").count() == 1

    def test_edit_validates_the_name(self, as_admin, make_game):
        game = make_game(name="Keep")
        as_admin.post(f"/admin/games/{game.id}/edit", data={"name": "x", "description": ""})
        assert _db.session.get(Game, game.id).name == "Keep"

    def test_only_implemented_unregistered_games_can_be_created(self, as_admin, make_game):
        make_game(name="Guess", slug="guess-the-number")

        as_admin.post("/admin/games/new", data={"slug": "made-up-game", "name": "Fake", "description": ""})
        as_admin.post("/admin/games/new", data={"slug": "guess-the-number", "name": "Dupe", "description": ""})
        assert Game.query.count() == 1

        as_admin.post("/admin/games/new", data={"slug": "logic-grid", "name": "Logic Grid", "description": "Deduce"})
        created = Game.query.filter_by(slug="logic-grid").one()
        assert created.category == "brain-lab"
        assert AuditLog.query.filter_by(action="game_created").count() == 1

    def test_toggle_is_audited(self, as_admin, make_game):
        game = make_game()
        as_admin.post(f"/admin/games/{game.id}/toggle")
        assert AuditLog.query.filter_by(action="game_disabled", target_id=game.id).count() == 1


class TestInactiveGamesAreUnplayable:

    def test_disabled_classic_game_redirects(self, client, make_user, make_game, login_as):
        make_game(name="Guess The Number", slug="guess-the-number", is_active=False)
        login_as(make_user())

        assert client.get("/guess").status_code == 302
        assert client.post("/guess/start", data={"difficulty": "easy"}).status_code == 302

    def test_disabled_brain_lab_game_returns_json_404_on_post(self, client, make_user, make_game, login_as):
        make_game(name="Memory Matrix", slug="memory-matrix", category="brain-lab", is_active=False)
        login_as(make_user())

        resp = client.post("/brain-lab/memory-matrix/start", json={"difficulty": "easy"})
        assert resp.status_code == 404
        assert resp.get_json()["error"]

    def test_active_game_still_loads(self, client, make_user, make_game, login_as):
        make_game(name="Guess The Number", slug="guess-the-number")
        login_as(make_user())
        assert client.get("/guess").status_code == 200

    def test_hub_pages_are_not_affected(self, client, make_user, login_as):
        login_as(make_user())
        assert client.get("/brain-lab/").status_code == 200


class TestShopManagement:

    def _create(self, client, **overrides):
        data = {"item_type": "frame", "name": "Ruby Frame", "description": "Red", "cost": "250", "asset": "frame-gold"}
        data.update(overrides)
        return client.post("/admin/shop/new", data=data)

    def test_create_valid_item(self, as_admin):
        self._create(as_admin)
        item = ShopItem.query.one()
        assert (item.item_type, item.cost, item.asset, item.is_active) == ("frame", 250, "frame-gold", True)
        assert AuditLog.query.filter_by(action="shop_item_created").count() == 1

    @pytest.mark.parametrize("overrides", [
        {"item_type": "weapon"},
        {"cost": "-1"},
        {"cost": "100001"},
        {"cost": "12.5"},
        {"asset": "frame-made-up"},
        {"asset": "../../etc/passwd"},
        {"item_type": "badge", "asset": "frame-gold"},
        {"item_type": "avatar", "asset": "not-there.png"},
        {"name": "x"},
    ])
    def test_invalid_items_are_rejected(self, as_admin, overrides):
        self._create(as_admin, **overrides)
        assert ShopItem.query.count() == 0

    def test_duplicate_name_is_rejected(self, as_admin, make_shop_item):
        make_shop_item(name="Ruby Frame", item_type="frame", asset="frame-gold")
        self._create(as_admin, name="ruby frame")
        assert ShopItem.query.count() == 1

    def test_avatar_must_be_a_real_file(self, as_admin):
        self._create(as_admin, item_type="avatar", name="Hero", asset="avatar3.png")
        assert ShopItem.query.one().asset == "avatar3.png"

    def test_booster_ignores_any_asset(self, as_admin):
        self._create(as_admin, item_type="booster", name="Boost", asset="frame-gold")
        assert ShopItem.query.one().asset is None

    def test_edit_cannot_change_type(self, as_admin, make_shop_item):
        item = make_shop_item(name="Star", item_type="badge", asset="star", cost=10)

        as_admin.post(f"/admin/shop/{item.id}/edit", data={
            "item_type": "avatar", "name": "Star Badge", "description": "", "cost": "20", "asset": "crown"
        })

        item = _db.session.get(ShopItem, item.id)
        assert (item.item_type, item.name, item.cost, item.asset) == ("badge", "Star Badge", 20, "crown")
        assert AuditLog.query.filter_by(action="shop_item_updated").count() == 1

    def test_editing_does_not_touch_ownership(self, as_admin, make_user, make_shop_item):
        from gaminghub.models.user_inventory import UserInventory
        from gaminghub.services import shop_service

        owner = make_user(username="owner", coins=500)
        item = make_shop_item(name="Gold Frame", item_type="frame", asset="frame-gold", cost=100)
        shop_service.purchase_item(owner, item.id)

        as_admin.post(f"/admin/shop/{item.id}/edit", data={"name": "Gold Frame", "description": "", "cost": "999", "asset": "frame-gold"})

        assert UserInventory.query.filter_by(user_id=owner.id, shop_item_id=item.id).count() == 1
        assert _db.session.get(User, owner.id).coins == 400


class TestAuditLog:

    def test_page_lists_entries_and_filters(self, as_admin, admin_user, make_user):
        target = make_user(username="target")
        as_admin.post(f"/admin/users/{target.id}/adjust", data={"coins": "5", "reason": "Gift"})
        as_admin.post(f"/admin/users/{target.id}/status", data={"status": "suspended", "reason": "Spam"})

        page = as_admin.get("/admin/audit")
        assert b"user_balance_adjusted" in page.data and b"user_status_changed" in page.data

        filtered = as_admin.get("/admin/audit?action=user_balance_adjusted")
        assert b"Gift" in filtered.data and b"Spam" not in filtered.data

    def test_there_is_no_way_to_edit_or_delete_entries(self, app):
        rules = [r for r in app.url_map.iter_rules() if "audit" in r.rule]
        assert [r.rule for r in rules] == ["/admin/audit"]
        assert rules[0].methods - {"HEAD", "OPTIONS"} == {"GET"}

    def test_audit_entries_never_contain_passwords(self, client, make_user, login_as):
        user = make_user(password="currentpass1")
        login_as(user)
        client.post("/account/password", data={
            "current_password": "currentpass1", "new_password": "sekretpass99", "confirm_password": "sekretpass99"
        })

        for entry in AuditLog.query.all():
            blob = f"{entry.details} {entry.reason} {entry.target_label}"
            assert "sekretpass99" not in blob and "currentpass1" not in blob


class TestPromoteAdminCli:

    def test_promotes_and_audits(self, app, make_user):
        user = make_user(username="founder")
        result = app.test_cli_runner().invoke(args=["promote-admin", "founder"])

        assert result.exit_code == 0, result.output
        assert _db.session.get(User, user.id).role == "admin"
        entry = AuditLog.query.filter_by(action="user_role_changed").one()
        assert entry.actor_id is None and entry.reason == "promote-admin CLI"

    def test_unknown_user_fails(self, app):
        result = app.test_cli_runner().invoke(args=["promote-admin", "ghost"])
        assert result.exit_code != 0
