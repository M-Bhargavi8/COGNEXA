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