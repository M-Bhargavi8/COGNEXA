from datetime import datetime, timedelta

from gaminghub.services import shop_service


class TestGetShopItems:

    def test_returns_only_active_items(self, make_shop_item):
        make_shop_item(name="Active", is_active=True)
        make_shop_item(name="Inactive", is_active=False)

        items = shop_service.get_shop_items()

        assert [i.name for i in items] == ["Active"]

    def test_filters_by_item_type(self, make_shop_item):
        make_shop_item(name="A", item_type="avatar")
        make_shop_item(name="B", item_type="frame")

        items = shop_service.get_shop_items(item_type="frame")

        assert [i.name for i in items] == ["B"]


class TestPurchaseItem:

    def test_deducts_coins_and_grants_a_cosmetic(self, make_user, make_shop_item, db):
        from gaminghub.models.user_inventory import UserInventory

        user = make_user(coins=100)
        item = make_shop_item(item_type="avatar", cost=40)

        success, message = shop_service.purchase_item(user, item.id)

        assert success is True
        assert user.coins == 60
        assert UserInventory.query.filter_by(user_id=user.id, shop_item_id=item.id).count() == 1

    def test_rejects_insufficient_funds(self, make_user, make_shop_item):
        user = make_user(coins=10)
        item = make_shop_item(cost=50)

        success, message = shop_service.purchase_item(user, item.id)

        assert success is False
        assert user.coins == 10
        assert "coins" in message.lower()

    def test_rejects_buying_an_already_owned_cosmetic_twice(self, make_user, make_shop_item):
        user = make_user(coins=1000)
        item = make_shop_item(item_type="avatar", cost=10)

        shop_service.purchase_item(user, item.id)
        success, message = shop_service.purchase_item(user, item.id)

        assert success is False
        assert user.coins == 990  # only charged once

    def test_boosters_can_be_bought_repeatedly_and_stack_duration(self, make_user, make_shop_item):
        user = make_user(coins=1000, xp_booster_expires_at=None)
        booster = make_shop_item(item_type="booster", cost=10)

        shop_service.purchase_item(user, booster.id)
        first_expiry = user.xp_booster_expires_at

        shop_service.purchase_item(user, booster.id)
        second_expiry = user.xp_booster_expires_at

        assert second_expiry > first_expiry  # stacked, not reset
        assert user.coins == 980

    def test_rejects_an_inactive_item(self, make_user, make_shop_item):
        user = make_user(coins=1000)
        item = make_shop_item(is_active=False)

        success, message = shop_service.purchase_item(user, item.id)

        assert success is False

    def test_rejects_a_nonexistent_item(self, make_user):
        user = make_user(coins=1000)
        success, message = shop_service.purchase_item(user, 999999)
        assert success is False


class TestEquipItem:

    def test_equipping_an_avatar_sets_it(self, make_user, make_shop_item, db):
        from gaminghub.models.user_inventory import UserInventory

        user = make_user()
        item = make_shop_item(item_type="avatar", asset="cool.png")
        db.session.add(UserInventory(user_id=user.id, shop_item_id=item.id))
        db.session.commit()

        success, message = shop_service.equip_item(user, item.id)

        assert success is True
        assert user.avatar == "cool.png"

    def test_cannot_equip_something_not_owned(self, make_user, make_shop_item):
        user = make_user()
        item = make_shop_item(item_type="frame", asset="frame-gold")

        success, message = shop_service.equip_item(user, item.id)

        assert success is False

    def test_boosters_cannot_be_equipped(self, make_user, make_shop_item):
        user = make_user()
        item = make_shop_item(item_type="booster")

        success, message = shop_service.equip_item(user, item.id)

        assert success is False


class TestUnequip:

    def test_clears_frame(self, make_user):
        user = make_user(equipped_frame="frame-gold")
        success, message = shop_service.unequip(user, "frame")
        assert success is True
        assert user.equipped_frame is None

    def test_clears_badge(self, make_user):
        user = make_user(equipped_badge="🏆")
        success, message = shop_service.unequip(user, "badge")
        assert success is True
        assert user.equipped_badge is None

    def test_avatar_cannot_be_unequipped(self, make_user):
        user = make_user()
        success, message = shop_service.unequip(user, "avatar")
        assert success is False


class TestIsBoosterActive:

    def test_false_with_no_booster(self, make_user):
        user = make_user(xp_booster_expires_at=None)
        assert shop_service.is_booster_active(user) is False

    def test_true_when_expiry_is_in_the_future(self, make_user):
        user = make_user(xp_booster_expires_at=datetime.utcnow() + timedelta(hours=1))
        assert shop_service.is_booster_active(user) is True

    def test_false_when_expiry_is_in_the_past(self, make_user):
        user = make_user(xp_booster_expires_at=datetime.utcnow() - timedelta(hours=1))
        assert shop_service.is_booster_active(user) is False
