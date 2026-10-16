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


XP_BOOSTER = {
    "duration_hours": 1,
    "multiplier": 2
}


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


FOCUS_SHIFT_DIFFICULTIES = {
    "easy": {"object_count": 6, "change_count": 1, "reveal_ms": 2500, "xp": 30, "coins": 40, "multiplier": 1},
    "medium": {"object_count": 9, "change_count": 1, "reveal_ms": 2000, "xp": 50, "coins": 70, "multiplier": 1.5},
    "hard": {"object_count": 12, "change_count": 2, "reveal_ms": 1800, "xp": 80, "coins": 110, "multiplier": 2},
    "expert": {"object_count": 16, "change_count": 2, "reveal_ms": 1500, "xp": 120, "coins": 160, "multiplier": 3}
}

# Colour slugs rather than emoji discs: the grid renders these as CSS
# dots, which stay perfectly circular and identically sized across
# platforms. Emoji rendering varies enough between fonts that two
# swatches could read as different shapes, not just different colours.
FOCUS_SHIFT_PALETTE = ["red", "orange", "amber", "green", "cyan", "violet", "white", "slate", "rose"]


SEQUENCE_BREAKER_DIFFICULTIES = {
    "easy": {"types": ["arithmetic"], "terms_shown": 4, "xp": 25, "coins": 35, "multiplier": 1},
    "medium": {"types": ["arithmetic", "letters"], "terms_shown": 4, "xp": 40, "coins": 55, "multiplier": 1.5},
    "hard": {"types": ["arithmetic", "letters", "geometric"], "terms_shown": 5, "xp": 65, "coins": 90, "multiplier": 2},
    "expert": {"types": ["geometric", "fibonacci", "letters"], "terms_shown": 5, "xp": 100, "coins": 140, "multiplier": 3}
}


CODE_BREAKER_DIFFICULTIES = {
    "easy": {"digits": 3, "attempts": 10, "xp": 40, "coins": 55, "multiplier": 1},
    "medium": {"digits": 4, "attempts": 10, "xp": 65, "coins": 90, "multiplier": 1.5},
    "hard": {"digits": 5, "attempts": 10, "xp": 100, "coins": 140, "multiplier": 2},
    "expert": {"digits": 6, "attempts": 12, "xp": 150, "coins": 200, "multiplier": 3}
}


DUAL_TASK_DIFFICULTIES = {
    "easy": {"sequence_length": 3, "reveal_ms": 2500, "xp": 35, "coins": 45, "multiplier": 1},
    "medium": {"sequence_length": 4, "reveal_ms": 2200, "xp": 55, "coins": 75, "multiplier": 1.5},
    "hard": {"sequence_length": 5, "reveal_ms": 2000, "xp": 85, "coins": 115, "multiplier": 2},
    "expert": {"sequence_length": 6, "reveal_ms": 1800, "xp": 130, "coins": 170, "multiplier": 3}
}


RISK_REWARD_DIFFICULTIES = {
    "easy": {"rounds": 8, "safe_gain": 20, "risk_win_chance": 0.6, "risk_gain": 60, "risk_loss": 30, "xp": 30, "coins": 40},
    "medium": {"rounds": 10, "safe_gain": 20, "risk_win_chance": 0.5, "risk_gain": 80, "risk_loss": 40, "xp": 50, "coins": 70},
    "hard": {"rounds": 12, "safe_gain": 20, "risk_win_chance": 0.45, "risk_gain": 100, "risk_loss": 50, "xp": 80, "coins": 110},
    "expert": {"rounds": 15, "safe_gain": 15, "risk_win_chance": 0.4, "risk_gain": 120, "risk_loss": 60, "xp": 120, "coins": 160}
}


LOGIC_GRID_DIFFICULTIES = {
    "easy": {"size": 3, "xp": 40, "coins": 55, "multiplier": 1},
    "medium": {"size": 4, "xp": 65, "coins": 90, "multiplier": 1.5},
    "hard": {"size": 5, "xp": 100, "coins": 140, "multiplier": 2},
    "expert": {"size": 6, "xp": 150, "coins": 200, "multiplier": 3}
}

LOGIC_GRID_PLAYERS = ["Alex", "Sam", "Jordan", "Casey", "Riley", "Morgan"]
LOGIC_GRID_GAMES = ["Chess", "Poker", "Darts", "Bowling", "Tennis", "Golf"]


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
    },
    {
        "game_slug": "focus-shift",
        "difficulty": None,
        "criteria": {"type": "score_at_least", "value": 80},
        "description": "Score 80+ in Focus Shift.",
        "xp": 100,
        "coins": 70
    },
    {
        "game_slug": "sequence-breaker",
        "difficulty": None,
        "criteria": {"type": "win"},
        "description": "Solve a Sequence Breaker puzzle.",
        "xp": 90,
        "coins": 65
    },
    {
        "game_slug": "code-breaker",
        "difficulty": None,
        "criteria": {"type": "win"},
        "description": "Crack a Code Breaker code.",
        "xp": 100,
        "coins": 75
    },
    {
        "game_slug": "dual-task",
        "difficulty": None,
        "criteria": {"type": "score_at_least", "value": 90},
        "description": "Score 90+ overall in Dual Task.",
        "xp": 110,
        "coins": 80
    },
    {
        "game_slug": "risk-reward",
        "difficulty": None,
        "criteria": {"type": "win"},
        "description": "Finish a Risk & Reward run at or above the safe-play baseline.",
        "xp": 100,
        "coins": 70
    },
    {
        "game_slug": "logic-grid",
        "difficulty": None,
        "criteria": {"type": "win"},
        "description": "Solve a Logic Grid puzzle completely.",
        "xp": 110,
        "coins": 80
    }
]