from flask import Blueprint, render_template
from flask_login import login_required

gamehub = Blueprint("gamehub", __name__)


@gamehub.route("/games")
@login_required
def games_home():

    return render_template("gameshub.html")