import random
from gaminghub.services.reward_service import award
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from flask_login import login_required, current_user

games = Blueprint("games", __name__)

from gaminghub.config.constants import (
    DIFFICULTIES,
    RPS_REWARD
)


@games.route("/guess", methods=["GET", "POST"])
@login_required
def guess():

    if "game" not in session:
        return render_template(
            "games/guessing.html",
            game=None,
            message=""
        )

    game = session["game"]
    message = ""

    if request.method == "POST":

        guess_val = int(request.form["guess"])
        secret = game["secret"]

        if guess_val < secret:

            message = "📉 Too Low!"
            game["attempts_left"] -= 1

            session["game"] = game
            session.modified = True

        elif guess_val > secret:

            message = "📈 Too High!"
            game["attempts_left"] -= 1

            session["game"] = game
            session.modified = True

        else:

            award(
                current_user,
                xp=game["xp"],
                coins=game["coins"],
                outcome="win"
            )

            session.pop("game")

            flash("🎉 Congratulations! You Won!", "success")

            return redirect(url_for("dashboard.dashboard_home"))

        if game["attempts_left"] <= 0:

            award(
                current_user,
                xp=0,
                coins=0,
                outcome="loss"
            )

            answer = game["secret"]

            session.pop("game")

            flash(
                f"💀 Game Over! The number was {answer}",
                "danger"
            )

            return redirect(url_for("games.guess"))

    return render_template(
        "games/guessing.html",
        game=game,
        message=message
    )


@games.route("/guess/start", methods=["POST"])
@login_required
def start_guess():

    difficulty = request.form.get("difficulty", "easy")

    settings = DIFFICULTIES[difficulty]

    session["game"] = {
        "secret": random.randint(1, 100),
        "difficulty": difficulty,
        "attempts_left": settings["attempts"],
        "max_attempts": settings["attempts"],
        "coins": settings["coins"],
        "xp": settings["xp"]
    }

    session.modified = True

    return redirect(url_for("games.guess"))

@games.route("/rps", methods=["GET", "POST"])
@login_required
def rps():

    import random

    choices = ["Rock", "Paper", "Scissors"]

    player = None
    computer = None
    result = None

    if request.method == "POST":

        player = request.form["choice"]

        computer = random.choice(choices)

        if player == computer:

            result = "Draw"

            award(
                current_user,
                xp=0,
                coins=0,
                outcome="draw"
            )

        elif (
            (player == "Rock" and computer == "Scissors")
            or
            (player == "Paper" and computer == "Rock")
            or
            (player == "Scissors" and computer == "Paper")
        ):

            result = "Win"

            award(
                current_user,
                xp=RPS_REWARD["xp"],
                coins=RPS_REWARD["coins"],
                outcome="win"
            )

        else:

            result = "Lose"

            award(
                current_user,
                xp=0,
                coins=0,
                outcome="loss"
            )

    return render_template(
        "games/rps.html",
        player=player,
        computer=computer,
        result=result
    )