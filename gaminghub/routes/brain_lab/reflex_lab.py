import random
from datetime import datetime

from flask import render_template, request, jsonify
from flask_login import login_required, current_user

from gaminghub.routes.brain_lab import brain_lab, outcome_extras
from gaminghub.services import game_service
from gaminghub.config.constants import REFLEX_LAB


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
            **outcome_extras(result)
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
        **outcome_extras(result)
    })
