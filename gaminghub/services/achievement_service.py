from gaminghub.database.database import db
from gaminghub.models.achievement import Achievement
from gaminghub.models.user_achievement import UserAchievement


def unlock(user, achievement_name):

    achievement = Achievement.query.filter_by(
        name=achievement_name
    ).first()

    if not achievement:
        return

    already = UserAchievement.query.filter_by(
        user_id=user.id,
        achievement_id=achievement.id
    ).first()

    if already:
        return

    db.session.add(UserAchievement(
        user_id=user.id,
        achievement_id=achievement.id
    ))

    user.coins += achievement.coin_reward
    user.xp += achievement.xp_reward

    db.session.commit()


def check_achievements(user):

    if user.games_played >= 1:
        unlock(user, "First Game")

    if user.wins >= 1:
        unlock(user, "First Win")

    if user.games_played >= 10:
        unlock(user, "Gamer")

    if user.level >= 5:
        unlock(user, "Rising Star")

    if user.coins >= 500:
        unlock(user, "Rich Player")
