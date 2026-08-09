from flask import Blueprint, render_template
from flask_login import login_required, current_user

from gaminghub.services.reward_service import xp_progress

dashboard = Blueprint("dashboard", __name__)

@dashboard.route("/dashboard")
@login_required
def dashboard_home():
    _, xp_needed, xp_percent = xp_progress(current_user)
    return render_template(
        "dashboard.html",
        xp_needed=xp_needed,
        xp_percent=xp_percent
    )