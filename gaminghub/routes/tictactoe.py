import random

from flask import Blueprint
from flask import render_template
from flask import request
from flask import flash

from flask_login import login_required
from flask_login import current_user

from gaminghub.services import game_service
from gaminghub.config.constants import TICTACTOE_REWARD

tictactoe = Blueprint("tictactoe", __name__)

WINS = [
    (0,1,2),
    (3,4,5),
    (6,7,8),
    (0,3,6),
    (1,4,7),
    (2,5,8),
    (0,4,8),
    (2,4,6)
]


def check(board, symbol):

    for a,b,c in WINS:
        if board[a]==board[b]==board[c]==symbol:
            return True

    return False


@tictactoe.route("/tictactoe", methods=["GET","POST"])
@login_required
def play():

    game = game_service.get_game("tic-tac-toe")
    session = game_service.get_active_session(current_user, game)

    if not session:
        session = game_service.start_session(
            current_user,
            "tic-tac-toe",
            state={"board": [""] * 9}
        )

    state = game_service.get_state(session)
    board = state["board"]
    result = None

    if request.method == "POST" and session.status == "active":

        try:
            move = int(request.form.get("move", -1))
        except ValueError:
            move = -1

        if move < 0 or move > 8 or board[move] != "":

            flash("Invalid move.", "warning")

        else:

            board[move] = "X"

            if check(board, "X"):

                result = "Win"

                game_service.complete_session(
                    session,
                    current_user,
                    outcome="win",
                    xp=TICTACTOE_REWARD["xp"],
                    coins=TICTACTOE_REWARD["coins"],
                    score=TICTACTOE_REWARD["xp"]
                )

            else:

                empty = [i for i, v in enumerate(board) if v == ""]

                if empty:
                    board[random.choice(empty)] = "O"

                if check(board, "O"):

                    result = "Lose"

                    game_service.complete_session(
                        session,
                        current_user,
                        outcome="loss",
                        xp=0,
                        coins=0,
                        score=0
                    )

                elif "" not in board:

                    result = "Draw"

                    game_service.complete_session(
                        session,
                        current_user,
                        outcome="draw",
                        xp=0,
                        coins=0,
                        score=0
                    )

            game_service.set_state(session, {"board": board})

    return render_template(
        "games/tictactoe.html",
        board=board,
        result=result
    )
