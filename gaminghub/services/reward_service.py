from datetime import date, datetime, timedelta

from gaminghub.database.database import db
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
            icon="⬆️", link="/dashboard"
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

    if user.last_claim == today - timedelta(days=1):
        user.daily_streak += 1
    else:
        user.daily_streak = 1

    reward = user.daily_streak * 20
    user.last_claim = today

    award(user, coins=reward)

    return True, f"🎁 Daily Reward Claimed! +{reward} Coins", reward
