from gaminghub.database.database import db
from gaminghub.models.achievement import Achievement
from gaminghub.models.user_achievement import UserAchievement
from gaminghub.models.game import Game


def unlock(user, achievement_name):
    """Returns the Achievement if newly unlocked, None otherwise (unknown name or already owned)."""

    achievement = Achievement.query.filter_by(
        name=achievement_name
    ).first()

    if not achievement:
        return None

    already = UserAchievement.query.filter_by(
        user_id=user.id,
        achievement_id=achievement.id
    ).first()

    if already:
        return None

    db.session.add(UserAchievement(
        user_id=user.id,
        achievement_id=achievement.id
    ))

    user.coins += achievement.coin_reward
    user.xp += achievement.xp_reward

    db.session.commit()

    return achievement


def check_achievements(user):
    """User-state achievements — no game result needed. Returns newly unlocked achievements."""

    unlocked = []

    def _try(name, condition):
        if condition:
            achievement = unlock(user, name)
            if achievement:
                unlocked.append(achievement)

    _try("First Game", user.games_played >= 1)
    _try("First Win", user.wins >= 1)
    _try("Gamer", user.games_played >= 10)
    _try("50 Games", user.games_played >= 50)
    _try("100 Games", user.games_played >= 100)
    _try("Rising Star", user.level >= 5)
    _try("Rich Player", user.coins >= 500)
    _try("7 Day Streak", user.daily_streak >= 7)

    return unlocked


def check_game_achievements(user, game_result):
    """Achievements that depend on a specific GameResult. Returns newly unlocked achievements."""

    unlocked = []
    game = Game.query.get(game_result.game_id)

    if not game:
        return unlocked

    def _try(name, condition):
        if condition:
            achievement = unlock(user, name)
            if achievement:
                unlocked.append(achievement)

    _try("Brain Trainer", game.category == "brain-lab")

    _try(
        "Perfect Recall",
        game.slug == "memory-matrix"
        and game_result.accuracy is not None
        and game_result.accuracy >= 1.0
    )

    _try(
        "Speed Demon",
        game.slug == "reflex-lab"
        and game_result.reaction_time is not None
        and game_result.reaction_time < 250
    )

    return unlocked
