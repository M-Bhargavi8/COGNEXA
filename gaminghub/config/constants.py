DIFFICULTIES = {

    "easy": {
        "attempts": 10,
        "coins": 30,
        "xp": 20
    },

    "medium": {
        "attempts": 7,
        "coins": 60,
        "xp": 40
    },

    "hard": {
        "attempts": 5,
        "coins": 120,
        "xp": 80
    }

}


LEVEL_XP = 100


RPS_REWARD = {
    "coins": 15,
    "xp": 20
}


TICTACTOE_REWARD = {
    "coins": 25,
    "xp": 30
}


MEMORY_MATRIX_DIFFICULTIES = {
    "easy": {
        "grid": 3,
        "pattern_count": 4,
        "reveal_ms": 3000,
        "xp": 30,
        "coins": 40,
        "multiplier": 1
    },
    "medium": {
        "grid": 4,
        "pattern_count": 6,
        "reveal_ms": 3000,
        "xp": 50,
        "coins": 70,
        "multiplier": 1.5
    },
    "hard": {
        "grid": 5,
        "pattern_count": 9,
        "reveal_ms": 3500,
        "xp": 80,
        "coins": 110,
        "multiplier": 2
    },
    "expert": {
        "grid": 6,
        "pattern_count": 13,
        "reveal_ms": 4000,
        "xp": 120,
        "coins": 160,
        "multiplier": 3
    }
}


REFLEX_LAB = {
    "min_delay_ms": 1500,
    "max_delay_ms": 4000,
    "min_valid_ms": 100,
    "max_valid_ms": 3000,
    "timing_tolerance_ms": 150,
    "good_reaction_ms": 400
}


CHALLENGE_TEMPLATES = [
    {
        "game_slug": "memory-matrix",
        "difficulty": "hard",
        "criteria": {"type": "win"},
        "description": "Win a Hard difficulty Memory Matrix round.",
        "xp": 150,
        "coins": 100
    },
    {
        "game_slug": "reflex-lab",
        "difficulty": None,
        "criteria": {"type": "score_at_least", "value": 700},
        "description": "Score 700+ in Reflex Lab (react in under 300ms).",
        "xp": 150,
        "coins": 100
    },
    {
        "game_slug": "guess-the-number",
        "difficulty": None,
        "criteria": {"type": "win"},
        "description": "Win a round of Guess The Number.",
        "xp": 80,
        "coins": 60
    },
    {
        "game_slug": "rock-paper-scissors",
        "difficulty": None,
        "criteria": {"type": "win"},
        "description": "Win a round of Rock Paper Scissors.",
        "xp": 60,
        "coins": 50
    },
    {
        "game_slug": "tic-tac-toe",
        "difficulty": None,
        "criteria": {"type": "win"},
        "description": "Beat the computer at Tic Tac Toe.",
        "xp": 80,
        "coins": 60
    }
]