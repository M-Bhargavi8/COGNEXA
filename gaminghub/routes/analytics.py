from flask import Blueprint, render_template
from flask_login import login_required, current_user

from gaminghub.services import analytics_service

analytics = Blueprint("analytics", __name__)


@analytics.route("/analytics")
@login_required
def analytics_home():

    return render_template(
        "analytics.html",
        overview=analytics_service.get_overview(current_user),
        activity=analytics_service.get_activity_over_time(current_user),
        per_game=analytics_service.get_per_game_breakdown(current_user),
        skill_profile=analytics_service.get_skill_profile(current_user),
        recommendations=analytics_service.get_recommendations(current_user)
    )
