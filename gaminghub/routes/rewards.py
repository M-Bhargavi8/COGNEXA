from flask import Blueprint, flash, redirect, url_for, render_template
from flask_login import login_required, current_user

from gaminghub.services import reward_service
from gaminghub.services import shop_service

rewards = Blueprint("rewards", __name__)


@rewards.route("/daily", methods=["POST"])
@login_required
def daily():
    """POST-only: claiming changes the account, so it must not be
    triggerable by a cross-site link or image tag."""

    success, message, _ = reward_service.claim_daily_reward(current_user)

    flash(message, "success" if success else "warning")

    return redirect(url_for("dashboard.dashboard_home"))


@rewards.route("/rewards/shop")
@login_required
def shop():

    items = shop_service.get_shop_items()
    owned_ids = shop_service.get_owned_item_ids(current_user)

    grouped = {"avatar": [], "frame": [], "badge": [], "booster": []}
    for item in items:
        grouped.setdefault(item.item_type, []).append(item)

    return render_template(
        "shop.html",
        grouped=grouped,
        owned_ids=owned_ids,
        booster_active=shop_service.is_booster_active(current_user)
    )


@rewards.route("/rewards/shop/buy/<int:item_id>", methods=["POST"])
@login_required
def buy(item_id):

    success, message = shop_service.purchase_item(current_user, item_id)
    flash(message, "success" if success else "danger")

    return redirect(url_for("rewards.shop"))


@rewards.route("/rewards/shop/equip/<int:item_id>", methods=["POST"])
@login_required
def equip(item_id):

    success, message = shop_service.equip_item(current_user, item_id)
    flash(message, "success" if success else "danger")

    return redirect(url_for("rewards.shop"))


@rewards.route("/rewards/shop/unequip/<item_type>", methods=["POST"])
@login_required
def unequip(item_type):

    success, message = shop_service.unequip(current_user, item_type)
    flash(message, "success" if success else "danger")

    return redirect(url_for("rewards.shop"))