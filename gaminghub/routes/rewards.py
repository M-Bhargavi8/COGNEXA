from datetime import date, timedelta

from flask import Blueprint, flash, redirect, url_for
from flask_login import login_required, current_user

from gaminghub.services.reward_service import award

rewards = Blueprint("rewards", __name__)


@rewards.route("/daily")
@login_required
def daily():

    today = date.today()

    if current_user.last_claim == today:

        flash("You already claimed today's reward!", "warning")

        return redirect(url_for("dashboard.dashboard_home"))

    if current_user.last_claim == today - timedelta(days=1):

        current_user.daily_streak += 1

    else:

        current_user.daily_streak = 1

    reward = current_user.daily_streak * 20

    current_user.last_claim = today

    award(current_user, coins=reward)

    flash(
        f"🎁 Daily Reward Claimed! +{reward} Coins",
        "success"
    )

    return redirect(url_for("dashboard.dashboard_home"))