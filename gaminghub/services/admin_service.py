import os
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy import func, or_

from gaminghub.database.database import db
from gaminghub.models.user import User, ACCOUNT_STATUSES, STATUS_ACTIVE
from gaminghub.models.game import Game
from gaminghub.models.game_session import GameSession
from gaminghub.models.game_result import GameResult
from gaminghub.models.shop_item import ShopItem
from gaminghub.models.user_inventory import UserInventory
from gaminghub.models.user_achievement import UserAchievement
from gaminghub.models.api_token import ApiToken
from gaminghub.services import audit_service
from gaminghub.services.leaderboard_service import TOTAL_XP_EXPR
from gaminghub.services.reward_service import _apply_level_ups


# Bounds for manual balance adjustments -- generous enough for any real
# correction, small enough that a typo can't mint an absurd balance.
MAX_COIN_ADJUSTMENT = 100_000
MAX_XP_ADJUSTMENT = 100_000

MAX_ITEM_COST = 100_000
SHOP_ITEM_TYPES = ("avatar", "frame", "badge", "booster")

# Assets the templates actually know how to render. A frame is a CSS
# class in cognexa.css, a badge is a slug the shop_badge macro in
# _icons.html maps to an icon, and an avatar is a file on disk -- an
# admin can only pick from these, never type an arbitrary value.
FRAME_ASSETS = ("frame-bronze", "frame-silver", "frame-gold", "frame-neon", "frame-diamond")
BADGE_ASSETS = ("crown", "fire", "star", "lightning", "target", "diamond")


# --------------------------------------------------------------- overview

def get_overview_stats():
    since_7d = datetime.utcnow() - timedelta(days=7)

    most_played = (
        db.session.query(Game.name, Game.icon, Game.slug, func.count(GameResult.id).label("plays"))
        .join(GameResult, GameResult.game_id == Game.id)
        .group_by(Game.id)
        .order_by(func.count(GameResult.id).desc())
        .first()
    )

    return {
        "total_users": User.query.count(),
        "total_admins": User.query.filter_by(role="admin").count(),
        "suspended_users": User.query.filter(User.status != STATUS_ACTIVE).count(),
        "new_users_7d": User.query.filter(User.created_at >= since_7d).count(),
        "total_games_played": GameResult.query.count(),
        "active_sessions": GameSession.query.filter_by(status="active").count(),
        "total_lifetime_xp": int(db.session.query(func.sum(TOTAL_XP_EXPR)).scalar() or 0),
        "most_played_game": {"name": most_played[0], "icon": most_played[1], "slug": most_played[2], "plays": most_played[3]} if most_played else None,
        "active_games": Game.query.filter_by(is_active=True).count(),
        "total_games": Game.query.count(),
        "active_shop_items": ShopItem.query.filter_by(is_active=True).count(),
        "total_shop_items": ShopItem.query.count(),
    }


def get_recent_signups(limit=5):
    return User.query.order_by(User.created_at.desc()).limit(limit).all()


def get_recent_results(limit=5):
    return (
        db.session.query(GameResult, User, Game)
        .join(User, GameResult.user_id == User.id)
        .join(Game, GameResult.game_id == Game.id)
        .order_by(GameResult.created_at.desc())
        .limit(limit)
        .all()
    )


# ------------------------------------------------------------------ users

def search_users(query=None, status=None):
    q = User.query

    if query:
        pattern = f"%{query}%"
        q = q.filter(or_(User.username.ilike(pattern), User.email.ilike(pattern)))

    if status in ACCOUNT_STATUSES:
        q = q.filter(User.status == status)

    return q.order_by(User.created_at.desc()).all()


def count_active_admins():
    return User.query.filter_by(role="admin", status=STATUS_ACTIVE).count()


def get_user_detail(user):
    return {
        "results_count": GameResult.query.filter_by(user_id=user.id).count(),
        "recent_results": (
            db.session.query(GameResult, Game)
            .join(Game, GameResult.game_id == Game.id)
            .filter(GameResult.user_id == user.id)
            .order_by(GameResult.created_at.desc())
            .limit(10)
            .all()
        ),
        "inventory_count": UserInventory.query.filter_by(user_id=user.id).count(),
        "achievements_count": UserAchievement.query.filter_by(user_id=user.id).count(),
        "api_tokens_count": ApiToken.query.filter_by(user_id=user.id).count(),
        "audit_entries": audit_service.entries_for_user(user),
    }


def _would_remove_last_admin(target_user):
    return target_user.is_admin and target_user.is_active and count_active_admins() <= 1


def set_user_role(actor, target_user, new_role):
    """Returns (success, message)."""

    if new_role not in ("player", "admin"):
        return False, "Invalid role."

    if actor.id == target_user.id:
        return False, "You can't change your own role."

    if target_user.role == new_role:
        return False, f"{target_user.username} is already {new_role}."

    if new_role != "admin" and _would_remove_last_admin(target_user):
        return False, "You can't demote the last active administrator."

    if new_role == "admin" and not target_user.is_active:
        return False, "Reactivate this account before making it an administrator."

    old_role = target_user.role
    target_user.role = new_role

    audit_service.record(
        "user_role_changed", actor=actor, target=target_user, commit=False,
        details={"from": old_role, "to": new_role}
    )
    db.session.commit()

    return True, f"{target_user.username} is now {new_role}."


def set_user_status(actor, target_user, new_status, reason):
    """Suspend, deactivate or reactivate an account. Nothing is deleted:
    the account's results, purchases and achievements stay, it just can't
    sign in or use the API (and drops off the leaderboards) until
    reactivated. Returns (success, message)."""

    reason = (reason or "").strip()

    if new_status not in ACCOUNT_STATUSES:
        return False, "Invalid status."

    if actor.id == target_user.id:
        return False, "You can't change the status of your own account."

    if target_user.status == new_status:
        return False, f"{target_user.username} is already {new_status}."

    if new_status != STATUS_ACTIVE:
        if len(reason) < 3:
            return False, "Give a reason (at least 3 characters)."
        if _would_remove_last_admin(target_user):
            return False, "You can't suspend the last active administrator."

    old_status = target_user.status
    target_user.status = new_status
    target_user.status_reason = reason[:255] or None
    target_user.status_changed_at = datetime.utcnow()

    if new_status != STATUS_ACTIVE:
        # Ends every existing browser session and API token right away,
        # not just at the next login.
        target_user.auth_version = (target_user.auth_version or 0) + 1
        ApiToken.query.filter_by(user_id=target_user.id).delete()

    audit_service.record(
        "user_status_changed", actor=actor, target=target_user, reason=reason, commit=False,
        details={"from": old_status, "to": new_status}
    )
    db.session.commit()

    return True, f"{target_user.username} is now {new_status}."


def _parse_int(raw, label):
    raw = (raw or "").strip()
    if raw in ("", "0", "+0", "-0"):
        return 0, None
    try:
        return int(raw), None
    except ValueError:
        return None, f"{label} must be a whole number."


def adjust_balance(actor, target_user, coins_raw, xp_raw, reason):
    """Manual coin/XP correction with a mandatory reason. Coins can go up
    or down (never below zero). XP can only be granted: XP is progress
    within the current level and is consumed on level-up, so there is no
    well-defined way to take it back. Returns (success, message)."""

    reason = (reason or "").strip()

    coins_delta, error = _parse_int(coins_raw, "Coins")
    if error:
        return False, error

    xp_delta, error = _parse_int(xp_raw, "XP")
    if error:
        return False, error

    if coins_delta == 0 and xp_delta == 0:
        return False, "Enter a coin or XP amount to adjust."

    if abs(coins_delta) > MAX_COIN_ADJUSTMENT:
        return False, f"Coin adjustments are limited to ±{MAX_COIN_ADJUSTMENT:,}."

    if xp_delta < 0:
        return False, "XP can only be granted, not removed."

    if xp_delta > MAX_XP_ADJUSTMENT:
        return False, f"XP grants are limited to {MAX_XP_ADJUSTMENT:,}."

    if len(reason) < 3:
        return False, "Give a reason (at least 3 characters)."

    coins_before = target_user.coins or 0
    level_before, xp_before = target_user.level, target_user.xp

    if coins_before + coins_delta < 0:
        return False, f"That would leave {target_user.username} with a negative balance ({coins_before} coins now)."

    target_user.coins = coins_before + coins_delta

    if xp_delta:
        target_user.xp = (target_user.xp or 0) + xp_delta
        _apply_level_ups(target_user)

    audit_service.record(
        "user_balance_adjusted", actor=actor, target=target_user, reason=reason, commit=False,
        details={
            "coins_delta": coins_delta, "coins_before": coins_before, "coins_after": target_user.coins,
            "xp_delta": xp_delta, "level_before": level_before, "xp_before": xp_before,
            "level_after": target_user.level, "xp_after": target_user.xp,
        }
    )
    db.session.commit()

    return True, f"Adjusted {target_user.username}: {coins_delta:+d} coins, {xp_delta:+d} XP."


# ------------------------------------------------------------------ games

def toggle_game_active(game, actor=None):
    game.is_active = not game.is_active

    if actor is not None:
        audit_service.record(
            "game_enabled" if game.is_active else "game_disabled",
            actor=actor, target=game, commit=False
        )

    db.session.commit()
    return game.is_active


def _validate_game_fields(name, description):
    name = (name or "").strip()
    description = (description or "").strip()

    if not 2 <= len(name) <= 100:
        return None, None, "Name must be 2-100 characters."

    if len(description) > 255:
        return None, None, "Description must be at most 255 characters."

    return name, description, None


def update_game(actor, game, name, description):
    """Only presentation fields are editable. The slug ties the record to
    its hard-coded implementation and the category drives the Brain Lab
    skill model, so neither can change here."""

    name, description, error = _validate_game_fields(name, description)
    if error:
        return False, error

    changed = {}
    for field, value in (("name", name), ("description", description)):
        if getattr(game, field) != value:
            changed[field] = {"from": getattr(game, field), "to": value}
            setattr(game, field, value)

    if not changed:
        return True, "No changes to save."

    audit_service.record("game_updated", actor=actor, target=game, commit=False, details=changed)
    db.session.commit()

    return True, f"Saved {game.name}."


def missing_game_slugs():
    """Implemented games with no database record yet (e.g. a fresh
    install that skipped seed_games.py). Only these can be created --
    a record without code behind it would be a dead card."""

    from gaminghub.services.game_service import GAME_PLAY_ENDPOINTS

    existing = {slug for (slug,) in Game.query.with_entities(Game.slug).all()}
    return [slug for slug in GAME_PLAY_ENDPOINTS if slug not in existing]


def create_game(actor, slug, name, description):
    from gaminghub.services.game_service import category_for_slug

    if slug not in missing_game_slugs():
        return None, "That game is either already registered or has no implementation."

    name, description, error = _validate_game_fields(name, description)
    if error:
        return None, error

    game = Game(name=name, slug=slug, description=description, category=category_for_slug(slug), is_active=True)
    db.session.add(game)
    db.session.flush()

    audit_service.record("game_created", actor=actor, target=game, commit=False, details={"slug": slug})
    db.session.commit()

    return game, f"Registered {game.name}."


# ------------------------------------------------------------------- shop

def avatar_assets():
    folder = os.path.join(current_app.static_folder, "images", "avatars")
    try:
        files = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".webp", ".jpg", ".jpeg"))]
    except OSError:
        return []

    def _order(name):
        digits = "".join(ch for ch in name if ch.isdigit())
        return (int(digits) if digits else 0, name)

    return sorted(files, key=_order)


def asset_choices(item_type):
    if item_type == "avatar":
        return avatar_assets()
    if item_type == "frame":
        return list(FRAME_ASSETS)
    if item_type == "badge":
        return list(BADGE_ASSETS)
    return []


def toggle_shop_item_active(item, actor=None):
    item.is_active = not item.is_active

    if actor is not None:
        audit_service.record(
            "shop_item_enabled" if item.is_active else "shop_item_disabled",
            actor=actor, target=item, commit=False
        )

    db.session.commit()
    return item.is_active


def _validate_shop_fields(item_type, name, description, cost_raw, asset, exclude_item=None):
    name = (name or "").strip()
    description = (description or "").strip()
    asset = (asset or "").strip() or None

    if item_type not in SHOP_ITEM_TYPES:
        return None, "Choose a valid item type."

    if not 2 <= len(name) <= 100:
        return None, "Name must be 2-100 characters."

    duplicate = ShopItem.query.filter(func.lower(ShopItem.name) == name.lower())
    if exclude_item is not None:
        duplicate = duplicate.filter(ShopItem.id != exclude_item.id)
    if db.session.query(duplicate.exists()).scalar():
        return None, "Another item already has that name."

    if len(description) > 255:
        return None, "Description must be at most 255 characters."

    try:
        cost = int((cost_raw or "").strip())
    except ValueError:
        return None, "Cost must be a whole number."

    if not 0 <= cost <= MAX_ITEM_COST:
        return None, f"Cost must be between 0 and {MAX_ITEM_COST:,}."

    if item_type == "booster":
        asset = None
    elif asset not in asset_choices(item_type):
        return None, f"Choose a valid {item_type} asset."

    return {"name": name, "description": description, "cost": cost, "asset": asset}, None


def create_shop_item(actor, item_type, name, description, cost_raw, asset):
    fields, error = _validate_shop_fields(item_type, name, description, cost_raw, asset)
    if error:
        return None, error

    item = ShopItem(item_type=item_type, is_active=True, **fields)
    db.session.add(item)
    db.session.flush()

    audit_service.record(
        "shop_item_created", actor=actor, target=item, commit=False,
        details={"item_type": item_type, "cost": fields["cost"], "asset": fields["asset"]}
    )
    db.session.commit()

    return item, f"Created {item.name}."


def update_shop_item(actor, item, name, description, cost_raw, asset):
    """item_type can't change after creation: owners' equipped values and
    the equip logic both depend on it."""

    fields, error = _validate_shop_fields(item.item_type, name, description, cost_raw, asset, exclude_item=item)
    if error:
        return False, error

    changed = {}
    for field, value in fields.items():
        if getattr(item, field) != value:
            changed[field] = {"from": getattr(item, field), "to": value}
            setattr(item, field, value)

    if not changed:
        return True, "No changes to save."

    audit_service.record("shop_item_updated", actor=actor, target=item, commit=False, details=changed)
    db.session.commit()

    return True, f"Saved {item.name}."
