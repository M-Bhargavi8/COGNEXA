import random

from flask import Blueprint
from flask import render_template
from flask import request

from flask_login import login_required
from flask_login import current_user

from gaminghub.database.database import db

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

            current_user.games_played+=1
            current_user.wins+=1
            current_user.coins+=25
            current_user.xp+=30

            db.session.commit()

        else:

            empty=[i for i,v in enumerate(board) if v==""]

            if empty:

                board[random.choice(empty)]="O"

            if check(board,"O"):

                result="Lose"

                current_user.games_played+=1
                current_user.losses+=1

                db.session.commit()

            elif "" not in board:

                result="Draw"

    return render_template(
        "games/tictactoe.html",
        board=board,
        result=result
    )