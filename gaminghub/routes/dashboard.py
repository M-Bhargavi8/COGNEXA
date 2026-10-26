from flask import Blueprint, render_template
from flask_login import login_required, current_user

from gaminghub.services.reward_service import xp_progress
from gaminghub.services import challenge_service, game_service, notification_service
from gaminghub.database.database import db
from gaminghub.models.game import Game

dashboard = Blueprint("dashboard", __name__)

@dashboard.route("/dashboard")
@login_required
def dashboard_home():
    _, xp_needed, xp_percent = xp_progress(current_user)

    notification_service.ensure_daily_reminders(current_user)

    challenge = challenge_service.get_today_challenge()
    challenge_game = db.session.get(Game, challenge.game_id) if challenge else None

    return render_template(
        "dashboard.html",
        xp_needed=xp_needed,
        xp_percent=xp_percent,
        challenge=challenge,
        challenge_game=challenge_game,
        challenge_done=challenge_service.has_completed_today(current_user) if challenge else False,
        challenge_url=game_service.get_play_url(challenge_game.slug) if challenge_game else None
    )