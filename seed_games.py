from gaminghub.database.database import db
from gaminghub.models.game import Game
from gaminghub import create_app

app = create_app()

GAMES = [
    (
        "Guess The Number",
        "guess-the-number",
        "Guess the secret number before you run out of attempts.",
        "classic-arcade",
        "🎯",
    ),
    (
        "Rock Paper Scissors",
        "rock-paper-scissors",
        "Beat the computer in a classic hand game.",
        "classic-arcade",
        "✊",
    ),
    (
        "Tic Tac Toe",
        "tic-tac-toe",
        "Beat the computer AI at Tic Tac Toe.",
        "classic-arcade",
        "❌",
    ),
]

with app.app_context():
    for name, slug, description, category, icon in GAMES:
        if not Game.query.filter_by(slug=slug).first():
            db.session.add(Game(
                name=name,
                slug=slug,
                description=description,
                category=category,
                icon=icon
            ))
    db.session.commit()
    print("Games seeded.")
