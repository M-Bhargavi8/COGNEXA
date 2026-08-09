import random

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from gaminghub.services import game_service
from gaminghub.utils.helpers import flash_game_outcome

games = Blueprint("games", __name__)

from gaminghub.config.constants import (
    DIFFICULTIES,
    RPS_REWARD
)


@games.route("/guess", methods=["GET", "POST"])
@login_required
def guess():

    game = game_service.get_game("guess-the-number")
    session = game_service.get_active_session(current_user, game)

    if not session:
        return render_template(
            "games/guessing.html",
            game=None,
            message=""
        )

    state = game_service.get_state(session)
    message = ""

    if request.method == "POST":

        try:
            guess_val = int(request.form["guess"])
        except (KeyError, ValueError):
            flash("Enter a valid number.", "warning")
            return render_template(
                "games/guessing.html",
                game=state,
                message=""
            )

        secret = state["secret"]

        if guess_val < secret:

            message = "📉 Too Low!"
            state["attempts_left"] -= 1

            game_service.set_state(session, state)

        elif guess_val > secret:

            message = "📈 Too High!"
            state["attempts_left"] -= 1

            game_service.set_state(session, state)

        else:

            reward = DIFFICULTIES[session.difficulty]
            attempts_used = state["max_attempts"] - state["attempts_left"] + 1

            outcome = game_service.complete_session(
                session,
                current_user,
                outcome="win",
                xp=reward["xp"],
                coins=reward["coins"],
                score=reward["xp"],
                attempts=attempts_used
            )

            flash("🎉 Congratulations! You Won!", "success")
            flash_game_outcome(outcome)

            return redirect(url_for("dashboard.dashboard_home"))

        if state["attempts_left"] <= 0:

            game_service.complete_session(
                session,
                current_user,
                outcome="loss",
                xp=0,
                coins=0,
                score=0,
                attempts=state["max_attempts"]
            )

            answer = secret

            flash(
                f"💀 Game Over! The number was {answer}",
                "danger"
            )

            return redirect(url_for("games.guess"))

    return render_template(
        "games/guessing.html",
        game=state,
        message=message
    )


@games.route("/guess/start", methods=["POST"])
@login_required
def start_guess():

    difficulty = request.form.get("difficulty", "easy")

    if difficulty not in DIFFICULTIES:
        flash("Invalid difficulty.", "danger")
        return redirect(url_for("games.guess"))

    settings = DIFFICULTIES[difficulty]

    game_service.start_session(
        current_user,
        "guess-the-number",
        difficulty=difficulty,
        state={
            "secret": random.randint(1, 100),
            "attempts_left": settings["attempts"],
            "max_attempts": settings["attempts"]
        }
    )

    return redirect(url_for("games.guess"))


@games.route("/rps", methods=["GET", "POST"])
@login_required
def rps():

    choices = ["Rock", "Paper", "Scissors"]

    player = None
    computer = None
    result = None

    if request.method == "POST":

        player = request.form.get("choice")

        if player not in choices:
            flash("Invalid choice.", "danger")
            return redirect(url_for("games.rps"))

        computer = random.choice(choices)

        session = game_service.start_session(current_user, "rock-paper-scissors")

        if player == computer:

            result = "Draw"

            game_service.complete_session(
                session,
                current_user,
                outcome="draw",
                xp=0,
                coins=0,
                score=0
            )

        elif (
            (player == "Rock" and computer == "Scissors")
            or
            (player == "Paper" and computer == "Rock")
            or
            (player == "Scissors" and computer == "Paper")
        ):

            result = "Win"

            outcome = game_service.complete_session(
                session,
                current_user,
                outcome="win",
                xp=RPS_REWARD["xp"],
                coins=RPS_REWARD["coins"],
                score=RPS_REWARD["xp"]
            )

            flash_game_outcome(outcome)

        else:

            result = "Lose"

            game_service.complete_session(
                session,
                current_user,
                outcome="loss",
                xp=0,
                coins=0,
                score=0
            )

    return render_template(
        "games/rps.html",
        player=player,
        computer=computer,
        result=result
    )
