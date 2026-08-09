from gaminghub.database.database import db
from gaminghub.models.achievement import Achievement
from gaminghub import create_app

app = create_app()

ACHIEVEMENTS = [
    ("First Game", "First Game", "Played your first game!", "🎮", 20, 0),
    ("First Win",  "First Victory", "Won your first game!", "🏆", 50, 50),
    ("Gamer",      "Gamer", "Played 10 games", "🎯", 0, 0),
    ("Rising Star","Rising Star", "Reached Level 5", "⭐", 0, 0),
    ("Rich Player","Rich Player", "Collected 500 Coins", "💰", 0, 0),
    ("50 Games", "Dedicated", "Played 50 games", "🎮", 100, 100),
    ("100 Games", "Centurion", "Played 100 games", "💯", 200, 200),
    ("7 Day Streak", "Week Warrior", "Logged a 7 day login streak", "🔥", 100, 100),
    ("Brain Trainer", "Brain Trainer", "Played a Brain Lab game", "🧠", 30, 20),
    ("Perfect Recall", "Perfect Recall", "100% accuracy in Memory Matrix", "🧩", 80, 60),
    ("Speed Demon", "Speed Demon", "Reacted in under 250ms in Reflex Lab", "⚡", 80, 60),
]

with app.app_context():
    for name, title, desc, badge, coins, xp in ACHIEVEMENTS:
        if not Achievement.query.filter_by(name=name).first():
            db.session.add(Achievement(
                name=name, title=title, description=desc,
                badge=badge, coin_reward=coins, xp_reward=xp
            ))
    db.session.commit()
    print("Achievements seeded.")