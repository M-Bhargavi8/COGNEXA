import random
import string

from flask import render_template, request, jsonify
from flask_login import login_required, current_user

from gaminghub.routes.brain_lab import brain_lab, outcome_extras
from gaminghub.services import game_service
from gaminghub.config.constants import SEQUENCE_BREAKER_DIFFICULTIES


def _gen_arithmetic(terms_shown):
    start = random.randint(1, 20)
    step = random.randint(2, 9)
    seq = [start + i * step for i in range(terms_shown)]
    answer = start + terms_shown * step
    return [str(n) for n in seq], str(answer)


def _gen_geometric(terms_shown):
    start = random.randint(1, 5)
    ratio = random.choice([2, 3])
    seq = [start * (ratio ** i) for i in range(terms_shown)]
    answer = start * (ratio ** terms_shown)
    return [str(n) for n in seq], str(answer)


def _gen_fibonacci(terms_shown):
    a, b = random.randint(1, 5), random.randint(1, 5)
    seq = [a, b]
    while len(seq) < terms_shown:
        seq.append(seq[-1] + seq[-2])
    answer = seq[-1] + seq[-2]
    return [str(n) for n in seq[:terms_shown]], str(answer)


def _gen_letters(terms_shown):
    for _ in range(10):
        start = random.randint(0, 3)
        gap = random.randint(1, 2)
        positions = [start]
        g = gap
        for _ in range(terms_shown - 1):
            positions.append(positions[-1] + g)
            g += 1
        next_pos = positions[-1] + g
        if next_pos <= 25:
            seq = [string.ascii_uppercase[p] for p in positions[:terms_shown]]
            return seq, string.ascii_uppercase[next_pos]
    return ["A", "B", "D", "G"], "K"


GENERATORS = {
    "arithmetic": _gen_arithmetic,
    "geometric": _gen_geometric,
    "fibonacci": _gen_fibonacci,
    "letters": _gen_letters
}


@brain_lab.route("/sequence-breaker")
@login_required
def sequence_breaker():
    return render_template("brain_lab/sequence_breaker.html")


@brain_lab.route("/sequence-breaker/start", methods=["POST"])
@login_required
def sequence_breaker_start():

    payload = request.get_json(silent=True) or {}
    difficulty = payload.get("difficulty", "easy")

    if difficulty not in SEQUENCE_BREAKER_DIFFICULTIES:
        return jsonify(success=False, error={"message": "Invalid difficulty."}), 400

    config = SEQUENCE_BREAKER_DIFFICULTIES[difficulty]
    seq_type = random.choice(config["types"])
    sequence, answer = GENERATORS[seq_type](config["terms_shown"])

    game_service.start_session(
        current_user,
        "sequence-breaker",
        difficulty=difficulty,
        state={"answer": answer}
    )

    return jsonify(success=True, data={
        "sequence": sequence,
        "type": seq_type
    })


@brain_lab.route("/sequence-breaker/submit", methods=["POST"])
@login_required
def sequence_breaker_submit():

    game = game_service.get_game("sequence-breaker")
    session = game_service.get_active_session(current_user, game)

    if not session:
        return jsonify(success=False, error={"message": "No active game."}), 400

    payload = request.get_json(silent=True) or {}
    submitted = str(payload.get("answer", "")).strip().upper()

    state = game_service.get_state(session)
    correct_answer = str(state["answer"]).strip().upper()
    config = SEQUENCE_BREAKER_DIFFICULTIES[session.difficulty]

    correct = submitted != "" and submitted == correct_answer

    score = round(100 * config["multiplier"]) if correct else 0
    xp = config["xp"] if correct else 0
    coins = config["coins"] if correct else 0
    outcome = "win" if correct else "loss"

    result = game_service.complete_session(
        session,
        current_user,
        outcome=outcome,
        xp=xp,
        coins=coins,
        score=score
    )

    if not result:
        return jsonify(success=False, error={"message": "This game session has already been completed."}), 400

    streak = game_service.get_current_streak(current_user, game)

    return jsonify(success=True, data={
        "correct": correct,
        "correct_answer": correct_answer,
        "score": score,
        "xp": xp,
        "coins": coins,
        "is_new_best": result["is_new_best"],
        "streak": streak,
        **outcome_extras(result)
    })
