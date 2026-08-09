import random

from flask import render_template, request, jsonify
from flask_login import login_required, current_user

from gaminghub.routes.brain_lab import brain_lab, outcome_extras
from gaminghub.services import game_service
from gaminghub.config.constants import FOCUS_SHIFT_DIFFICULTIES, FOCUS_SHIFT_PALETTE


@brain_lab.route("/focus-shift")
@login_required
def focus_shift():
    return render_template("brain_lab/focus_shift.html")


@brain_lab.route("/focus-shift/start", methods=["POST"])
@login_required
def focus_shift_start():

    payload = request.get_json(silent=True) or {}
    difficulty = payload.get("difficulty", "easy")

    if difficulty not in FOCUS_SHIFT_DIFFICULTIES:
        return jsonify(success=False, error={"message": "Invalid difficulty."}), 400

    config = FOCUS_SHIFT_DIFFICULTIES[difficulty]

    original = [random.choice(FOCUS_SHIFT_PALETTE) for _ in range(config["object_count"])]
    changed_positions = random.sample(range(config["object_count"]), config["change_count"])

    changed = original[:]
    for pos in changed_positions:
        choices = [c for c in FOCUS_SHIFT_PALETTE if c != original[pos]]
        changed[pos] = random.choice(choices)

    game_service.start_session(
        current_user,
        "focus-shift",
        difficulty=difficulty,
        state={"changed_positions": changed_positions}
    )

    return jsonify(success=True, data={
        "original": original,
        "changed": changed,
        "reveal_ms": config["reveal_ms"]
    })


@brain_lab.route("/focus-shift/submit", methods=["POST"])
@login_required
def focus_shift_submit():

    game = game_service.get_game("focus-shift")
    session = game_service.get_active_session(current_user, game)

    if not session:
        return jsonify(success=False, error={"message": "No active game."}), 400

    payload = request.get_json(silent=True) or {}
    submitted = set(payload.get("selected", []))

    state = game_service.get_state(session)
    changed = set(state["changed_positions"])
    config = FOCUS_SHIFT_DIFFICULTIES[session.difficulty]

    hits = len(submitted & changed)
    false_positives = len(submitted - changed)

    accuracy = (hits - false_positives) / len(changed) if changed else 0.0
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
        "changed_positions": list(changed),
        **outcome_extras(result)
    })
