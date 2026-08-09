import random

from flask import Blueprint
from flask import render_template
from flask import request

from flask_login import login_required
from flask_login import current_user

from gaminghub.services.reward_service import award
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

    board=[""]*9

    result=None

    if request.method=="POST":

        board=request.form.getlist("board")

        move=int(request.form["move"])

        board[move]="X"

        if check(board,"X"):

            result="Win"

            award(
                current_user,
                xp=TICTACTOE_REWARD["xp"],
                coins=TICTACTOE_REWARD["coins"],
                outcome="win"
            )

        else:

            empty=[i for i,v in enumerate(board) if v==""]

            if empty:

                board[random.choice(empty)]="O"

            if check(board,"O"):

                result="Lose"

                award(
                    current_user,
                    xp=0,
                    coins=0,
                    outcome="loss"
                )

            elif "" not in board:

                result="Draw"

                award(
                    current_user,
                    xp=0,
                    coins=0,
                    outcome="draw"
                )

    return render_template(
        "games/tictactoe.html",
        board=board,
        result=result
    )