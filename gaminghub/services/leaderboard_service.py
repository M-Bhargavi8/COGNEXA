from datetime import datetime, timedelta

from sqlalchemy import func, desc

from gaminghub.database.database import db
from gaminghub.models.user import User
from gaminghub.models.game import Game
from gaminghub.models.game_result import GameResult
from gaminghub.config.constants import LEVEL_XP


# User.xp is progress *within* the current level (it resets on every
# level-up), not lifetime total XP -- so it can't be used directly to
# rank players. This reconstructs true lifetime XP analytically from
# (level, xp): reaching level L costs LEVEL_XP * (1+2+...+(L-1)) xp,
# which is LEVEL_XP * L * (L-1) / 2, plus whatever xp they've earned
# since. No new column needed, and it's a real SQL expression the
# database can sort by directly.
TOTAL_XP_EXPR = User.xp + (LEVEL_XP * User.level * (User.level - 1)) / 2


def _total_xp(user):
    return user.xp + LEVEL_XP * user.level * (user.level - 1) // 2


def _period_start(period):
    now = datetime.utcnow()

    if period == "daily":
        return datetime(now.year, now.month, now.day)
    if period == "weekly":
        return now - timedelta(days=7)

    raise ValueError("period must be 'daily' or 'weekly'")


def _ranked_leaderboard(value_query, limit):
    rows = (
        db.session.query(User, value_query.c.value)
        .join(value_query, value_query.c.user_id == User.id)
        .order_by(desc(value_query.c.value))
        .limit(limit)
        .all()
    )

    return [{"rank": i + 1, "user": u, "value": v or 0} for i, (u, v) in enumerate(rows)]


def _my_rank(value_query, my_value):
    if not my_value:
        return None

    higher = (
        db.session.query(func.count())
        .select_from(value_query)
        .filter(value_query.c.value > my_value)
        .scalar()
    )

    return higher + 1


def get_global_leaderboard(limit=20):
    rows = (
        db.session.query(User, TOTAL_XP_EXPR.label("total_xp"))
        .order_by(desc("total_xp"))
        .limit(limit)
        .all()
    )

    return [{"rank": i + 1, "user": u, "value": int(txp)} for i, (u, txp) in enumerate(rows)]


def get_my_global_rank(user):
    higher = db.session.query(func.count(User.id)).filter(TOTAL_XP_EXPR > _total_xp(user)).scalar()
    return higher + 1


def get_period_leaderboard(period, limit=20):
    since = _period_start(period)

    subq = (
        db.session.query(
            GameResult.user_id.label("user_id"),
            func.sum(GameResult.xp_earned).label("value")
        )
        .filter(GameResult.created_at >= since)
        .group_by(GameResult.user_id)
        .subquery()
    )

    return _ranked_leaderboard(subq, limit)


def get_my_period_rank(user, period):
    since = _period_start(period)

    my_value = (
        db.session.query(func.sum(GameResult.xp_earned))
        .filter(GameResult.user_id == user.id, GameResult.created_at >= since)
        .scalar()
    )

    subq = (
        db.session.query(
            GameResult.user_id.label("user_id"),
            func.sum(GameResult.xp_earned).label("value")
        )
        .filter(GameResult.created_at >= since)
        .group_by(GameResult.user_id)
        .subquery()
    )

    return _my_rank(subq, my_value), (my_value or 0)


def get_game_leaderboard(game, limit=20):
    subq = (
        db.session.query(
            GameResult.user_id.label("user_id"),
            func.max(GameResult.score).label("value")
        )
        .filter(GameResult.game_id == game.id)
        .group_by(GameResult.user_id)
        .subquery()
    )

    return _ranked_leaderboard(subq, limit)


def get_my_game_rank(user, game):
    my_value = (
        db.session.query(func.max(GameResult.score))
        .filter(GameResult.user_id == user.id, GameResult.game_id == game.id)
        .scalar()
    )

    subq = (
        db.session.query(
            GameResult.user_id.label("user_id"),
            func.max(GameResult.score).label("value")
        )
        .filter(GameResult.game_id == game.id)
        .group_by(GameResult.user_id)
        .subquery()
    )

    return _my_rank(subq, my_value), my_value


def get_category_leaderboard(category, limit=20):
    subq = (
        db.session.query(
            GameResult.user_id.label("user_id"),
            func.sum(GameResult.score).label("value")
        )
        .join(Game, Game.id == GameResult.game_id)
        .filter(Game.category == category)
        .group_by(GameResult.user_id)
        .subquery()
    )

    return _ranked_leaderboard(subq, limit)


def get_my_category_rank(user, category):
    my_value = (
        db.session.query(func.sum(GameResult.score))
        .join(Game, Game.id == GameResult.game_id)
        .filter(GameResult.user_id == user.id, Game.category == category)
        .scalar()
    )

    subq = (
        db.session.query(
            GameResult.user_id.label("user_id"),
            func.sum(GameResult.score).label("value")
        )
        .join(Game, Game.id == GameResult.game_id)
        .filter(Game.category == category)
        .group_by(GameResult.user_id)
        .subquery()
    )

    return _my_rank(subq, my_value), (my_value or 0)
