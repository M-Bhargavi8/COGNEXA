import random

from flask import render_template, request, jsonify
from flask_login import login_required, current_user

from gaminghub.routes.brain_lab import brain_lab, outcome_extras
from gaminghub.services import game_service
from gaminghub.config.constants import LOGIC_GRID_DIFFICULTIES, LOGIC_GRID_PLAYERS, LOGIC_GRID_GAMES


def generate_puzzle(size):
    """
    Picks a random solution first, then derives clues from it: direct
    "X plays Y" statements for all but the last 2 players, and a single
    exclusion clue for the final pair -- with only 2 players and 2
    games left undetermined, one true negative fact is always enough
    to force the last assignment. Guarantees a solvable, unique puzzle
    by construction rather than needing a constraint solver to verify it.
    """

    players = LOGIC_GRID_PLAYERS[:size]
    games = LOGIC_GRID_GAMES[:size]

    shuffled_games = games[:]
    random.shuffle(shuffled_games)
    solution = dict(zip(players, shuffled_games))

    order = players[:]
    random.shuffle(order)

    clues = [f"{player} plays {solution[player]}." for player in order[:-2]]

    hint_players = order[-2:]
    p1, p2 = hint_players
    clues.append(f"{p1} does not play {solution[p2]}.")

    random.shuffle(clues)

    return players, games, solution, clues, hint_players


@brain_lab.route("/logic-grid")
@login_required
def logic_grid():
    return render_template("brain_lab/logic_grid.html")


@brain_lab.route("/logic-grid/start", methods=["POST"])
@login_required
def logic_grid_start():

    payload = request.get_json(silent=True) or {}
    difficulty = payload.get("difficulty", "easy")

    if difficulty not in LOGIC_GRID_DIFFICULTIES:
        return jsonify(success=False, error={"message": "Invalid difficulty."}), 400

    config = LOGIC_GRID_DIFFICULTIES[difficulty]
    players, games, solution, clues, hint_players = generate_puzzle(config["size"])

    game_service.start_session(
        current_user,
        "logic-grid",
        difficulty=difficulty,
        state={
            "solution": solution,
            "hint_players": hint_players,
            "hints_used": 0,
            "hints_given": []
        }
    )

    return jsonify(success=True, data={
        "players": players,
        "games": games,
        "clues": clues
    })


@brain_lab.route("/logic-grid/hint", methods=["POST"])
@login_required
def logic_grid_hint():

    game = game_service.get_game("logic-grid")
    session = game_service.get_active_session(current_user, game)

    if not session:
        return jsonify(success=False, error={"message": "No active game."}), 400

    state = game_service.get_state(session)
    remaining = [p for p in state["hint_players"] if p not in state["hints_given"]]

    if not remaining:
        return jsonify(success=False, error={"message": "No more hints available."}), 400

    player = remaining[0]
    state["hints_given"].append(player)
    state["hints_used"] += 1

    game_service.set_state(session, state)

    return jsonify(success=True, data={
        "player": player,
        "game": state["solution"][player],
        "hints_used": state["hints_used"]
    })


@brain_lab.route("/logic-grid/submit", methods=["POST"])
@login_required
def logic_grid_submit():

    game = game_service.get_game("logic-grid")
    session = game_service.get_active_session(current_user, game)

    if not session:
        return jsonify(success=False, error={"message": "No active game."}), 400

    payload = request.get_json(silent=True) or {}
    submitted = payload.get("answers", {})

    state = game_service.get_state(session)
    solution = state["solution"]
    config = LOGIC_GRID_DIFFICULTIES[session.difficulty]

    correct_count = sum(
        1 for player, game_name in solution.items()
        if submitted.get(player) == game_name
    )

    total = len(solution)
    accuracy = correct_count / total if total else 0.0
    hint_penalty = max(0.3, 1 - state["hints_used"] * 0.2)

    score = round(accuracy * 100 * config["multiplier"] * hint_penalty)
    xp = round(config["xp"] * accuracy * hint_penalty)
    coins = round(config["coins"] * accuracy * hint_penalty)
    outcome = "win" if correct_count == total else "loss"

    result = game_service.complete_session(
        session,
        current_user,
        outcome=outcome,
        xp=xp,
        coins=coins,
        score=score,
        accuracy=accuracy,
        mistakes=total - correct_count
    )

    if not result:
        return jsonify(success=False, error={"message": "This game session has already been completed."}), 400

    return jsonify(success=True, data={
        "correct_count": correct_count,
        "total": total,
        "accuracy": round(accuracy * 100),
        "solution": solution,
        "hints_used": state["hints_used"],
        "score": score,
        "xp": xp,
        "coins": coins,
        "is_new_best": result["is_new_best"],
        **outcome_extras(result)
    })
