from gaminghub.models.achievement import Achievement
from gaminghub.database import db


def unlock(user, title, description, badge):

    already = Achievement.query.filter_by(
        user_id=user.id,
        title=title
    ).first()

    if already:
        return

    achievement = Achievement(
        user_id=user.id,
        title=title,
        description=description,
        badge=badge
    )

    db.session.add(achievement)

    def check(user):
        if user.games_played >= 1:
            unlock(
            user,
            "First Game",
            "Played your first game",
            "🥉"
        )

    if user.wins >= 10:
        unlock(
            user,
            "Winner",
            "Won 10 games",
            "🥈"
        )

    if user.wins >= 50:
        unlock(
            user,
            "Champion",
            "Won 50 games",
            "🥇"
        )

    if user.coins >= 500:
        unlock(
            user,
            "Rich",
            "Collected 500 coins",
            "💰"
        )

    if user.level >= 5:
        unlock(
            user,
            "Level Master",
            "Reached Level 5",
            "⭐"
        )
        