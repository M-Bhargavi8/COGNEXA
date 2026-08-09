import random

from flask import render_template, request, jsonify
from flask_login import login_required, current_user

from gaminghub.routes.brain_lab import brain_lab, outcome_extras
from gaminghub.services import game_service
from gaminghub.config.constants import DUAL_TASK_DIFFICULTIES


def _generate_math_problem(difficulty):

    if difficulty in ("easy", "medium"):
        a, b = random.randint(2, 12), random.randint(2, 12)
    else:
        a, b = random.randint(10, 25), random.randint(2, 12)

    op = random.choice(["+", "-", "*"])

    if op == "+":
        answer = a + b
    elif op == "-":
        a, b = max(a, b), min(a, b)
        answer = a - b
    else:
        answer = a * b

    return f"{a} {op} {b}", answer


@brain_lab.route("/dual-task")
@login_required
def dual_task():
    return render_template("brain_lab/dual_task.html")


@brain_lab.route("/dual-task/start", methods=["POST"])
@login_required
def dual_task_start():

    payload = request.get_json(silent=True) or {}
    difficulty = payload.get("difficulty", "easy")

    if difficulty not in DUAL_TASK_DIFFICULTIES:
        return jsonify(success=False, error={"message": "Invalid difficulty."}), 400

    config = DUAL_TASK_DIFFICULTIES[difficulty]

    sequence = [random.randint(0, 9) for _ in range(config["sequence_length"])]
    problem_text, math_answer = _generate_math_problem(difficulty)

    game_service.start_session(
        current_user,
        "dual-task",
        difficulty=difficulty,
        state={"sequence": sequence, "math_answer": math_answer}
    )

    return jsonify(success=True, data={
        "sequence": sequence,
        "reveal_ms": config["reveal_ms"],
        "math_problem": problem_text
    })


@brain_lab.route("/dual-task/submit", methods=["POST"])
@login_required
def dual_task_submit():

    game = game_service.get_game("dual-task")
    session = game_service.get_active_session(current_user, game)

    if not session:
        return jsonify(success=False, error={"message": "No active game."}), 400

    payload = request.get_json(silent=True) or {}
    submitted_math = payload.get("math_answer")
    submitted_sequence = payload.get("sequence_recall", [])

    state = game_service.get_state(session)
    config = DUAL_TASK_DIFFICULTIES[session.difficulty]
    original_sequence = state["sequence"]

    try:
        math_correct = int(submitted_math) == state["math_answer"]
    except (TypeError, ValueError):
        math_correct = False

    hits = sum(1 for a, b in zip(submitted_sequence, original_sequence) if a == b)
    memory_accuracy = hits / len(original_sequence) if original_sequence else 0.0

    math_score = 100 if math_correct else 0
    overall = round((memory_accuracy * 100 + math_score) / 2)

    score = round(overall * config["multiplier"])
    xp = round(config["xp"] * overall / 100)
    coins = round(config["coins"] * overall / 100)
    outcome = "win" if overall >= 50 else "loss"

    result = game_service.complete_session(
        session,
        current_user,
        outcome=outcome,
        xp=xp,
        coins=coins,
        score=score,
        accuracy=memory_accuracy,
        mistakes=0 if math_correct else 1
    )

    if not result:
        return jsonify(success=False, error={"message": "This game session has already been completed."}), 400

    streak = game_service.get_current_streak(current_user, game)

    return jsonify(success=True, data={
        "math_correct": math_correct,
        "math_answer": state["math_answer"],
        "memory_accuracy": round(memory_accuracy * 100),
        "original_sequence": original_sequence,
        "overall": overall,
        "score": score,
        "xp": xp,
        "coins": coins,
        "is_new_best": result["is_new_best"],
        "streak": streak,
        **outcome_extras(result)
    })
