from gaminghub.database.database import db
from gaminghub.utils.achievement_engine import check_achievements


def reward_player(user, xp, coins, win=False):

    user.games_played += 1

    if win:
        user.wins += 1
    else:
        user.losses += 1

    user.xp += xp
    user.coins += coins

    if xp > user.high_score:
        user.high_score = xp

    while user.xp >= user.level * 100:
        user.xp -= user.level * 100
        user.level += 1

    db.session.commit()
    check_achievements(user)