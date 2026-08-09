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
    (
        "Memory Matrix",
        "memory-matrix",
        "Memorize the pattern before it disappears, then reproduce it.",
        "brain-lab",
        "🧩",
    ),
    (
        "Reflex Lab",
        "reflex-lab",
        "Wait for the signal, then click as fast as you can.",
        "brain-lab",
        "⚡",
    ),
    (
        "Focus Shift",
        "focus-shift",
        "Spot which object changed before it's gone.",
        "brain-lab",
        "👁️",
    ),
    (
        "Sequence Breaker",
        "sequence-breaker",
        "Crack the pattern and predict what comes next.",
        "brain-lab",
        "🔢",
    ),
    (
        "Code Breaker",
        "code-breaker",
        "Deduce the secret code from position and digit clues.",
        "brain-lab",
        "🔐",
    ),
    (
        "Dual Task",
        "dual-task",
        "Hold a sequence in memory while solving a math problem.",
        "brain-lab",
        "🧮",
    ),
    (
        "Risk & Reward",
        "risk-reward",
        "Play it safe or push your luck across a run of decisions.",
        "brain-lab",
        "🎲",
    ),
    (
        "Logic Grid",
        "logic-grid",
        "Use the clues to deduce who's who.",
        "brain-lab",
        "🧭",
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
