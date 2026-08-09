import random

from flask import render_template, request, jsonify
from flask_login import login_required, current_user

from gaminghub.routes.brain_lab import brain_lab, outcome_extras
from gaminghub.services import game_service
from gaminghub.config.constants import MEMORY_MATRIX_DIFFICULTIES


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
        **outcome_extras(result)
    })
