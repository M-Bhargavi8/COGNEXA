from datetime import datetime, timedelta

from gaminghub.database.database import db
from gaminghub.models.shop_item import ShopItem
from gaminghub.models.user_inventory import UserInventory
from gaminghub.config.constants import XP_BOOSTER


def get_shop_items(item_type=None):
    query = ShopItem.query.filter_by(is_active=True)

    if item_type:
        query = query.filter_by(item_type=item_type)

    return query.order_by(ShopItem.item_type, ShopItem.cost).all()


def get_owned_item_ids(user):
    rows = UserInventory.query.filter_by(user_id=user.id).with_entities(UserInventory.shop_item_id).all()
    return {row[0] for row in rows}


def is_booster_active(user):
    return bool(user.xp_booster_expires_at and user.xp_booster_expires_at > datetime.utcnow())


def purchase_item(user, item_id):
    """Returns (success, message)."""

    item = ShopItem.query.filter_by(id=item_id, is_active=True).first()

    if not item:
        return False, "Item not found."

    if item.item_type != "booster":
        already_owned = UserInventory.query.filter_by(user_id=user.id, shop_item_id=item.id).first()
        if already_owned:
            return False, "You already own this."

    if user.coins < item.cost:
        return False, "Not enough coins."

    user.coins -= item.cost

    if item.item_type == "booster":
        base = user.xp_booster_expires_at if is_booster_active(user) else datetime.utcnow()
        user.xp_booster_expires_at = base + timedelta(hours=XP_BOOSTER["duration_hours"])
    else:
        db.session.add(UserInventory(user_id=user.id, shop_item_id=item.id))

    db.session.commit()

    return True, f"Purchased {item.name}!"


def equip_item(user, item_id):
    """Returns (success, message)."""

    item = ShopItem.query.filter_by(id=item_id, is_active=True).first()

    if not item:
        return False, "Item not found."

    if item.item_type == "booster":
        return False, "Boosters activate automatically on purchase."

    owned = UserInventory.query.filter_by(user_id=user.id, shop_item_id=item.id).first()

    if not owned:
        return False, "You don't own this item."

    if item.item_type == "avatar":
        user.avatar = item.asset
    elif item.item_type == "frame":
        user.equipped_frame = item.asset
    elif item.item_type == "badge":
        user.equipped_badge = item.asset

    db.session.commit()

    return True, f"Equipped {item.name}."


def unequip(user, item_type):
    """Returns (success, message). Only frame/badge can be cleared -- avatar always needs a value."""

    if item_type == "frame":
        user.equipped_frame = None
    elif item_type == "badge":
        user.equipped_badge = None
    else:
        return False, "Can't remove this."

    db.session.commit()

    return True, "Removed."
