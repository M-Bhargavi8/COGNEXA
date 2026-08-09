import random
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from gaminghub.services import game_service
from gaminghub.models.game import Game
from gaminghub.config.constants import MEMORY_MATRIX_DIFFICULTIES, REFLEX_LAB

brain_lab = Blueprint("brain_lab", __name__, url_prefix="/brain-lab")


def _outcome_extras(outcome):
    """JSON-serializable achievements/challenge info from a complete_session() result."""

    challenge = outcome.get("challenge_completed")

    return {
        "achievements_unlocked": [
            {"title": a.title, "badge": a.badge}
            for a in outcome.get("achievements_unlocked", [])
        ],
        "challenge_completed": {
            "description": challenge.description,
            "xp": challenge.xp_reward,
            "coins": challenge.coin_reward
        } if challenge else None
    }


@brain_lab.route("/")
@login_required
def hub():

    games = Game.query.filter_by(
        category="brain-lab",
        is_active=True
    ).all()

    game_cards = [
        {"game": g, "url": game_service.get_play_url(g.slug)}
        for g in games
    ]

    game_cards = [c for c in game_cards if c["url"]]

    return render_template("brain_lab/hub.html", game_cards=game_cards)


# ---------- Memory Matrix ----------

@brain_lab.route("/memory-matrix")
@login_required
def memory_matrix():
    return render_template("brain_lab/memory_matrix.html")


@brain_lab.route("/memory-matrix/start", methods=["POST"])
@login_required
def memory_matrix_start():

    payload = request.get_json(silent=True) or {}
    difficulty = payload.get("difficulty", "easy")

    if difficulty not in MEMORY_MATRIX_DIFFICULTIES:
        return jsonify(success=False, error={"message": "Invalid difficulty."}), 400

    config = MEMORY_MATRIX_DIFFICULTIES[difficulty]
    total_cells = config["grid"] * config["grid"]

    pattern = random.sample(range(total_cells), config["pattern_count"])

    game_service.start_session(
        current_user,
        "memory-matrix",
        difficulty=difficulty,
        state={"pattern": pattern}
    )

    return jsonify(success=True, data={
        "pattern": pattern,
        "grid": config["grid"],
        "reveal_ms": config["reveal_ms"]
    })


@brain_lab.route("/memory-matrix/submit", methods=["POST"])
@login_required
def memory_matrix_submit():

    game = game_service.get_game("memory-matrix")
    session = game_service.get_active_session(current_user, game)

    if not session:
        return jsonify(success=False, error={"message": "No active game."}), 400

    payload = request.get_json(silent=True) or {}
    submitted = set(payload.get("selected", []))

    state = game_service.get_state(session)
    pattern = set(state["pattern"])
    config = MEMORY_MATRIX_DIFFICULTIES[session.difficulty]

    hits = len(submitted & pattern)
    false_positives = len(submitted - pattern)

    accuracy = (hits - false_positives) / len(pattern) if pattern else 0.0
    accuracy = max(0.0, min(accuracy, 1.0))

    score = round(accuracy * 100 * config["multiplier"])
    xp = round(config["xp"] * accuracy)
    coins = round(config["coins"] * accuracy)
    outcome = "win" if accuracy >= 0.5 else "loss"

    result = game_service.complete_session(
        session,
        current_user,
        outcome=outcome,
        xp=xp,
        coins=coins,
        score=score,
        accuracy=accuracy,
        mistakes=false_positives
    )

    if not result:
        return jsonify(success=False, error={"message": "This game session has already been completed."}), 400

    streak = game_service.get_current_streak(current_user, game)

    return jsonify(success=True, data={
        "accuracy": round(accuracy * 100),
        "score": score,
        "xp": xp,
        "coins": coins,
        "is_new_best": result["is_new_best"],
        "streak": streak,
        **_outcome_extras(result)
    })


# ---------- Reflex Lab ----------

@brain_lab.route("/reflex-lab")
@login_required
def reflex_lab():
    return render_template("brain_lab/reflex_lab.html")


@brain_lab.route("/reflex-lab/start", methods=["POST"])
@login_required
def reflex_lab_start():

    delay_ms = random.randint(
        REFLEX_LAB["min_delay_ms"],
        REFLEX_LAB["max_delay_ms"]
    )

    game_service.start_session(
        current_user,
        "reflex-lab",
        state={"delay_ms": delay_ms}
    )

    return jsonify(success=True, data={"delay_ms": delay_ms})


@brain_lab.route("/reflex-lab/submit", methods=["POST"])
@login_required
def reflex_lab_submit():

    game = game_service.get_game("reflex-lab")
    session = game_service.get_active_session(current_user, game)

    if not session:
        return jsonify(success=False, error={"message": "No active game."}), 400

    payload = request.get_json(silent=True) or {}
    early = bool(payload.get("early"))
    reaction_ms = payload.get("reaction_ms")

    state = game_service.get_state(session)
    elapsed_ms = (datetime.utcnow() - session.started_at).total_seconds() * 1000

    valid = (
        not early
        and isinstance(reaction_ms, (int, float))
        and REFLEX_LAB["min_valid_ms"] <= reaction_ms <= REFLEX_LAB["max_valid_ms"]
        and elapsed_ms >= state["delay_ms"] - REFLEX_LAB["timing_tolerance_ms"]
    )

    if not valid:

        result = game_service.complete_session(
            session,
            current_user,
            outcome="loss",
            xp=0,
            coins=0,
            score=0
        )

        if not result:
            return jsonify(success=False, error={"message": "This game session has already been completed."}), 400

        return jsonify(success=True, data={
            "valid": False,
            "reason": "too_soon" if early else "invalid_timing",
            **_outcome_extras(result)
        })

    score = max(0, round(1000 - reaction_ms))
    xp = round(score / 20)
    coins = round(score / 15)
    outcome = "win" if reaction_ms < REFLEX_LAB["good_reaction_ms"] else "loss"

    result = game_service.complete_session(
        session,
        current_user,
        outcome=outcome,
        xp=xp,
        coins=coins,
        score=score,
        reaction_time=reaction_ms
    )

    if not result:
        return jsonify(success=False, error={"message": "This game session has already been completed."}), 400

    stats = game_service.get_reaction_stats(current_user, game)

    return jsonify(success=True, data={
        "valid": True,
        "reaction_ms": reaction_ms,
        "score": score,
        "xp": xp,
        "coins": coins,
        "is_new_best": result["is_new_best"],
        "best_reaction_ms": stats["best"],
        **_outcome_extras(result)
    })
