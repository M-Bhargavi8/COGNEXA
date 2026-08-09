from gaminghub.database.database import db
from gaminghub.config.constants import LEVEL_XP
from gaminghub.services.achievement_service import check_achievements


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

    if outcome is not None:

        user.games_played += 1

        if outcome == "win":
            user.wins += 1
        elif outcome == "loss":
            user.losses += 1
        # "draw" still counts as a game played, but isn't a win or a loss

    user.xp += xp
    user.coins += coins

    if xp > user.high_score:
        user.high_score = xp

    _apply_level_ups(user)

    db.session.commit()

    return check_achievements(user)
