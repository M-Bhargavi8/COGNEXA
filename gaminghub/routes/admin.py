from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from gaminghub.utils.decorators import admin_required
from gaminghub.services import admin_service
from gaminghub.models.user import User
from gaminghub.models.game import Game
from gaminghub.models.shop_item import ShopItem

admin = Blueprint("admin", __name__, url_prefix="/admin")


@admin.route("/")
@login_required
@admin_required
def admin_dashboard():
    return render_template(
        "admin/dashboard.html",
        stats=admin_service.get_overview_stats(),
        recent_signups=admin_service.get_recent_signups(),
        recent_results=admin_service.get_recent_results()
    )


@admin.route("/users")
@login_required
@admin_required
def users():
    query = request.args.get("q", "").strip()

    return render_template(
        "admin/users.html",
        users=admin_service.search_users(query or None),
        query=query
    )


@admin.route("/users/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def toggle_user_role(user_id):
    target = User.query.get_or_404(user_id)
    new_role = "player" if target.role == "admin" else "admin"

    success, message = admin_service.set_user_role(current_user, target, new_role)
    flash(message, "success" if success else "danger")

    return redirect(url_for("admin.users", q=request.args.get("q", "")))


@admin.route("/games")
@login_required
@admin_required
def games():
    return render_template(
        "admin/games.html",
        games=Game.query.order_by(Game.category, Game.name).all()
    )


@admin.route("/games/<int:game_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_game(game_id):
    game = Game.query.get_or_404(game_id)
    is_active = admin_service.toggle_game_active(game)

    flash(f"{game.name} is now {'active' if is_active else 'inactive'}.", "success")

    return redirect(url_for("admin.games"))


@admin.route("/shop")
@login_required
@admin_required
def shop():
    return render_template(
        "admin/shop.html",
        items=ShopItem.query.order_by(ShopItem.item_type, ShopItem.name).all()
    )


@admin.route("/shop/<int:item_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_shop_item(item_id):
    item = ShopItem.query.get_or_404(item_id)
    is_active = admin_service.toggle_shop_item_active(item)

    flash(f"{item.name} is now {'active' if is_active else 'inactive'}.", "success")

    return redirect(url_for("admin.shop"))
