from datetime import date, datetime, timedelta

from sqlalchemy import or_, update

from gaminghub.database.database import db
from gaminghub.models.user import User
from gaminghub.config.constants import LEVEL_XP, XP_BOOSTER
from gaminghub.services.achievement_service import check_achievements
from gaminghub.services import notification_service


def _apply_level_ups(user):

    while user.xp >= user.level * LEVEL_XP:
        user.xp -= user.level * LEVEL_XP
        user.level += 1


def xp_progress(user):
    """Return (xp_into_level, xp_needed_for_level, percent) for progress bars."""

    needed = user.level * LEVEL_XP
    percent = round((user.xp / needed) * 100) if needed else 0

    return user.xp, needed, percent


def award(user, *, xp=0, coins=0, outcome=None):
    """
    Single authoritative entry point for granting XP/coins and recording
    game outcomes. Every game/route should call this instead of mutating
    User fields directly, so level-ups and achievement checks always run
    the same way regardless of which game granted the reward.

    outcome: "win" | "loss" | "draw" | None
        None leaves games_played/wins/losses untouched (e.g. non-game
        rewards like the daily streak claim).

    Returns the list of newly-unlocked Achievements (may be empty).
    """

    if xp and user.xp_booster_expires_at and user.xp_booster_expires_at > datetime.utcnow():
        xp *= XP_BOOSTER["multiplier"]

    if outcome is not None:

        user.games_played += 1

        if outcome == "win":
            user.wins += 1
        elif outcome == "loss":
            user.losses += 1
        # "draw" still counts as a game played, but isn't a win or a loss

    level_before = user.level

    user.xp += xp
    user.coins += coins

    if xp > user.high_score:
        user.high_score = xp

    _apply_level_ups(user)

    db.session.commit()

    if user.level > level_before:
        notification_service.create(
            user, "level_up", f"Level Up! You reached Level {user.level}",
            icon="level-up", link="/dashboard"
        )

    achievements_unlocked = check_achievements(user)
    notification_service.notify_achievements(user, achievements_unlocked)

    return achievements_unlocked


def claim_daily_reward(user):
    """
    Returns (success, message, coins_awarded). Centralizes the streak
    bookkeeping so the web /daily route and the REST API's daily-claim
    endpoint share one implementation instead of two copies that could
    drift apart.
    """

    today = date.today()

    if user.last_claim == today:
        return False, "You already claimed today's reward!", 0

    streak = (user.daily_streak or 0) + 1 if user.last_claim == today - timedelta(days=1) else 1

    # Two claims racing each other would both pass the check above. The
    # conditional UPDATE lets exactly one of them record today's claim;
    # the other finds last_claim already set and gets nothing.
    claimed = db.session.execute(
        update(User)
        .where(User.id == user.id, or_(User.last_claim.is_(None), User.last_claim != today))
        .values(last_claim=today, daily_streak=streak)
        .execution_options(synchronize_session=False)
    ).rowcount == 1

    if not claimed:
        db.session.rollback()
        return False, "You already claimed today's reward!", 0

    user.daily_streak = streak
    user.last_claim = today

    reward = streak * 20

    award(user, coins=reward)

    return True, f"Daily Reward Claimed! +{reward} Coins", reward
