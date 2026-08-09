import random

from flask import render_template, request, jsonify
from flask_login import login_required, current_user

from gaminghub.routes.brain_lab import brain_lab, outcome_extras
from gaminghub.services import game_service
from gaminghub.config.constants import CODE_BREAKER_DIFFICULTIES


def _score_guess(secret, guess):
    correct_position = sum(1 for s, g in zip(secret, guess) if s == g)
    correct_digit = len(set(secret) & set(guess)) - correct_position
    return correct_position, correct_digit


@brain_lab.route("/code-breaker")
@login_required
def code_breaker():
    return render_template("brain_lab/code_breaker.html")


@brain_lab.route("/code-breaker/start", methods=["POST"])
@login_required
def code_breaker_start():

    payload = request.get_json(silent=True) or {}
    difficulty = payload.get("difficulty", "easy")

    if difficulty not in CODE_BREAKER_DIFFICULTIES:
        return jsonify(success=False, error={"message": "Invalid difficulty."}), 400

    config = CODE_BREAKER_DIFFICULTIES[difficulty]
    secret = random.sample(range(10), config["digits"])

    game_service.start_session(
        current_user,
        "code-breaker",
        difficulty=difficulty,
        state={
            "secret": secret,
            "attempts_left": config["attempts"],
            "max_attempts": config["attempts"],
            "history": []
        }
    )

    return jsonify(success=True, data={
        "digits": config["digits"],
        "max_attempts": config["attempts"]
    })


@brain_lab.route("/code-breaker/guess", methods=["POST"])
@login_required
def code_breaker_guess():

    game = game_service.get_game("code-breaker")
    session = game_service.get_active_session(current_user, game)

    if not session:
        return jsonify(success=False, error={"message": "No active game."}), 400

    state = game_service.get_state(session)
    config = CODE_BREAKER_DIFFICULTIES[session.difficulty]
    digits = config["digits"]

    payload = request.get_json(silent=True) or {}
    raw_guess = payload.get("guess", [])

    try:
        guess = [int(d) for d in raw_guess]
    except (TypeError, ValueError):
        return jsonify(success=False, error={"message": "Guess must be digits."}), 400

    if (
        len(guess) != digits
        or len(set(guess)) != digits
        or any(d < 0 or d > 9 for d in guess)
    ):
        return jsonify(success=False, error={"message": f"Enter {digits} unique digits (0-9)."}), 400

    secret = state["secret"]
    correct_position, correct_digit = _score_guess(secret, guess)

    state["attempts_left"] -= 1
    state["history"].append({
        "guess": guess,
        "correct_position": correct_position,
        "correct_digit": correct_digit
    })

    won = correct_position == digits
    game_over = won or state["attempts_left"] <= 0

    if not game_over:
        game_service.set_state(session, state)

        return jsonify(success=True, data={
            "correct_position": correct_position,
            "correct_digit": correct_digit,
            "won": False,
            "game_over": False,
            "attempts_left": state["attempts_left"]
        })

    attempts_used = config["attempts"] - state["attempts_left"]

    if won:
        efficiency = max(10, 100 - (attempts_used - 1) * 10)
        score = round(efficiency * config["multiplier"])
        xp = round(config["xp"] * efficiency / 100)
        coins = round(config["coins"] * efficiency / 100)
        outcome = "win"
    else:
        score, xp, coins = 0, 0, 0
        outcome = "loss"

    result = game_service.complete_session(
        session,
        current_user,
        outcome=outcome,
        xp=xp,
        coins=coins,
        score=score,
        attempts=attempts_used
    )

    if not result:
        return jsonify(success=False, error={"message": "This game session has already been completed."}), 400

    return jsonify(success=True, data={
        "correct_position": correct_position,
        "correct_digit": correct_digit,
        "won": won,
        "game_over": True,
        "secret": secret,
        "attempts_used": attempts_used,
        "score": score,
        "xp": xp,
        "coins": coins,
        "is_new_best": result["is_new_best"],
        **outcome_extras(result)
    })
