import random

from flask import render_template, request, jsonify
from flask_login import login_required, current_user

from gaminghub.routes.brain_lab import brain_lab, outcome_extras
from gaminghub.services import game_service
from gaminghub.config.constants import RISK_REWARD_DIFFICULTIES


@brain_lab.route("/risk-reward")
@login_required
def risk_reward():
    return render_template("brain_lab/risk_reward.html")


@brain_lab.route("/risk-reward/start", methods=["POST"])
@login_required
def risk_reward_start():

    payload = request.get_json(silent=True) or {}
    difficulty = payload.get("difficulty", "easy")

    if difficulty not in RISK_REWARD_DIFFICULTIES:
        return jsonify(success=False, error={"message": "Invalid difficulty."}), 400

    config = RISK_REWARD_DIFFICULTIES[difficulty]

    game_service.start_session(
        current_user,
        "risk-reward",
        difficulty=difficulty,
        state={
            "round": 0,
            "score": 0,
            "decisions": 0,
            "risk_decisions": 0,
            "risk_successes": 0
        }
    )

    return jsonify(success=True, data={
        "rounds": config["rounds"],
        "safe_gain": config["safe_gain"],
        "risk_gain": config["risk_gain"],
        "risk_loss": config["risk_loss"]
    })


@brain_lab.route("/risk-reward/decide", methods=["POST"])
@login_required
def risk_reward_decide():

    game = game_service.get_game("risk-reward")
    session = game_service.get_active_session(current_user, game)

    if not session:
        return jsonify(success=False, error={"message": "No active game."}), 400

    payload = request.get_json(silent=True) or {}
    choice = payload.get("choice")

    if choice not in ("safe", "risk"):
        return jsonify(success=False, error={"message": "Choice must be 'safe' or 'risk'."}), 400

    state = game_service.get_state(session)
    config = RISK_REWARD_DIFFICULTIES[session.difficulty]

    if state["round"] >= config["rounds"]:
        return jsonify(success=False, error={"message": "This game session has already been completed."}), 400

    round_outcome = "safe"

    if choice == "safe":
        state["score"] += config["safe_gain"]
    else:
        state["risk_decisions"] += 1
        won_risk = random.random() < config["risk_win_chance"]
        if won_risk:
            state["score"] += config["risk_gain"]
            state["risk_successes"] += 1
            round_outcome = "risk_win"
        else:
            state["score"] = max(0, state["score"] - config["risk_loss"])
            round_outcome = "risk_loss"

    state["decisions"] += 1
    state["round"] += 1

    game_over = state["round"] >= config["rounds"]

    if not game_over:
        game_service.set_state(session, state)

        return jsonify(success=True, data={
            "round_outcome": round_outcome,
            "score": state["score"],
            "round": state["round"],
            "rounds": config["rounds"],
            "game_over": False
        })

    baseline = config["rounds"] * config["safe_gain"]
    performance_ratio = min(2.0, state["score"] / baseline) if baseline else 0
    xp = round(config["xp"] * performance_ratio)
    coins = round(config["coins"] * performance_ratio)
    outcome = "win" if state["score"] >= baseline else "loss"

    result = game_service.complete_session(
        session,
        current_user,
        outcome=outcome,
        xp=xp,
        coins=coins,
        score=state["score"],
        attempts=state["risk_decisions"]
    )

    if not result:
        return jsonify(success=False, error={"message": "This game session has already been completed."}), 400

    risk_success_rate = (
        round(100 * state["risk_successes"] / state["risk_decisions"])
        if state["risk_decisions"] else None
    )

    return jsonify(success=True, data={
        "round_outcome": round_outcome,
        "score": state["score"],
        "round": state["round"],
        "rounds": config["rounds"],
        "game_over": True,
        "decisions": state["decisions"],
        "risk_decisions": state["risk_decisions"],
        "risk_success_rate": risk_success_rate,
        "xp": xp,
        "coins": coins,
        "is_new_best": result["is_new_best"],
        **outcome_extras(result)
    })
