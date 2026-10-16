from datetime import datetime, timedelta

from sqlalchemy import func

from gaminghub.database.database import db
from gaminghub.models.user import User
from gaminghub.models.game import Game
from gaminghub.models.game_session import GameSession
from gaminghub.models.game_result import GameResult
from gaminghub.models.shop_item import ShopItem
from gaminghub.services.leaderboard_service import TOTAL_XP_EXPR


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


def search_users(query=None):
    q = User.query

    if query:
        q = q.filter(User.username.ilike(f"%{query}%"))

    return q.order_by(User.created_at.desc()).all()


def set_user_role(actor, target_user, new_role):
    """Returns (success, message). An admin can't change their own role --
    the only way to reach this route is to already be an admin, so this
    guard alone is enough to guarantee the app always keeps at least one."""

    if new_role not in ("player", "admin"):
        return False, "Invalid role."

    if actor.id == target_user.id:
        return False, "You can't change your own role."

    target_user.role = new_role
    db.session.commit()

    return True, f"{target_user.username} is now {new_role}."


def toggle_game_active(game):
    game.is_active = not game.is_active
    db.session.commit()
    return game.is_active


def toggle_shop_item_active(item):
    item.is_active = not item.is_active
    db.session.commit()
    return item.is_active
