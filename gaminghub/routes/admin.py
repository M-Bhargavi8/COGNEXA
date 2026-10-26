from flask import Blueprint, abort, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from gaminghub.database.database import db
from gaminghub.utils.decorators import admin_required
from gaminghub.services import admin_service, audit_service
from gaminghub.models.user import User, ACCOUNT_STATUSES
from gaminghub.models.game import Game
from gaminghub.models.shop_item import ShopItem

admin = Blueprint("admin", __name__, url_prefix="/admin")


@admin.before_request
@login_required
@admin_required
def _require_admin():
    """Every admin route requires an active admin session. Checking here
    as well as on each view means a route added later can't forget it."""


def _get_or_404(model, object_id):
    obj = db.session.get(model, object_id)
    if obj is None:
        abort(404)
    return obj


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


# ------------------------------------------------------------------ users

@admin.route("/users")
@login_required
@admin_required
def users():
    query = request.args.get("q", "").strip()[:100]
    status = request.args.get("status", "")

    return render_template(
        "admin/users.html",
        users=admin_service.search_users(query or None, status or None),
        query=query,
        status=status if status in ACCOUNT_STATUSES else "",
        statuses=ACCOUNT_STATUSES,
    )


@admin.route("/users/<int:user_id>")
@login_required
@admin_required
def user_detail(user_id):
    target = _get_or_404(User, user_id)

    return render_template(
        "admin/user_detail.html",
        target=target,
        detail=admin_service.get_user_detail(target),
        statuses=ACCOUNT_STATUSES,
        parse_details=audit_service.parse_details,
        max_coins=admin_service.MAX_COIN_ADJUSTMENT,
        max_xp=admin_service.MAX_XP_ADJUSTMENT,
    )


@admin.route("/users/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def toggle_user_role(user_id):
    target = _get_or_404(User, user_id)
    new_role = "player" if target.role == "admin" else "admin"

    success, message = admin_service.set_user_role(current_user, target, new_role)
    flash(message, "success" if success else "danger")

    if request.form.get("return_to") == "detail":
        return redirect(url_for("admin.user_detail", user_id=target.id))

    return redirect(url_for("admin.users", q=request.args.get("q", "")))


@admin.route("/users/<int:user_id>/status", methods=["POST"])
@login_required
@admin_required
def set_user_status(user_id):
    target = _get_or_404(User, user_id)

    success, message = admin_service.set_user_status(
        current_user, target, request.form.get("status"), request.form.get("reason")
    )
    flash(message, "success" if success else "danger")

    return redirect(url_for("admin.user_detail", user_id=target.id))


@admin.route("/users/<int:user_id>/adjust", methods=["POST"])
@login_required
@admin_required
def adjust_user_balance(user_id):
    target = _get_or_404(User, user_id)

    success, message = admin_service.adjust_balance(
        current_user, target,
        request.form.get("coins"), request.form.get("xp"), request.form.get("reason")
    )
    flash(message, "success" if success else "danger")

    return redirect(url_for("admin.user_detail", user_id=target.id))


# ------------------------------------------------------------------ games

@admin.route("/games")
@login_required
@admin_required
def games():
    return render_template(
        "admin/games.html",
        games=Game.query.order_by(Game.category, Game.name).all(),
        missing_slugs=admin_service.missing_game_slugs(),
    )


@admin.route("/games/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_game():
    missing = admin_service.missing_game_slugs()

    if request.method == "POST":
        game, message = admin_service.create_game(
            current_user, request.form.get("slug"), request.form.get("name"), request.form.get("description")
        )
        flash(message, "success" if game else "danger")
        if game:
            return redirect(url_for("admin.games"))

    if not missing:
        flash("Every implemented game is already registered.", "info")
        return redirect(url_for("admin.games"))

    return render_template("admin/game_form.html", game=None, missing_slugs=missing, form=request.form)


@admin.route("/games/<int:game_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_game(game_id):
    game = _get_or_404(Game, game_id)

    if request.method == "POST":
        success, message = admin_service.update_game(
            current_user, game, request.form.get("name"), request.form.get("description")
        )
        flash(message, "success" if success else "danger")
        if success:
            return redirect(url_for("admin.games"))
        db.session.rollback()

    return render_template("admin/game_form.html", game=game, missing_slugs=[], form=request.form)


@admin.route("/games/<int:game_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_game(game_id):
    game = _get_or_404(Game, game_id)
    is_active = admin_service.toggle_game_active(game, actor=current_user)

    flash(f"{game.name} is now {'active' if is_active else 'inactive'}.", "success")

    return redirect(url_for("admin.games"))


# ------------------------------------------------------------------- shop

def _asset_options():
    return {t: admin_service.asset_choices(t) for t in admin_service.SHOP_ITEM_TYPES}


@admin.route("/shop")
@login_required
@admin_required
def shop():
    return render_template(
        "admin/shop.html",
        items=ShopItem.query.order_by(ShopItem.item_type, ShopItem.name).all()
    )


@admin.route("/shop/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_shop_item():
    if request.method == "POST":
        item, message = admin_service.create_shop_item(
            current_user, request.form.get("item_type"), request.form.get("name"),
            request.form.get("description"), request.form.get("cost"), request.form.get("asset")
        )
        flash(message, "success" if item else "danger")
        if item:
            return redirect(url_for("admin.shop"))

    return render_template(
        "admin/shop_form.html", item=None, form=request.form,
        item_types=admin_service.SHOP_ITEM_TYPES, asset_options=_asset_options(),
        max_cost=admin_service.MAX_ITEM_COST,
    )


@admin.route("/shop/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_shop_item(item_id):
    item = _get_or_404(ShopItem, item_id)

    if request.method == "POST":
        success, message = admin_service.update_shop_item(
            current_user, item, request.form.get("name"), request.form.get("description"),
            request.form.get("cost"), request.form.get("asset")
        )
        flash(message, "success" if success else "danger")
        if success:
            return redirect(url_for("admin.shop"))
        db.session.rollback()

    return render_template(
        "admin/shop_form.html", item=item, form=request.form,
        item_types=admin_service.SHOP_ITEM_TYPES, asset_options=_asset_options(),
        max_cost=admin_service.MAX_ITEM_COST,
    )


@admin.route("/shop/<int:item_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_shop_item(item_id):
    item = _get_or_404(ShopItem, item_id)
    is_active = admin_service.toggle_shop_item_active(item, actor=current_user)

    flash(f"{item.name} is now {'active' if is_active else 'inactive'}.", "success")

    return redirect(url_for("admin.shop"))


# ------------------------------------------------------------------ audit

@admin.route("/audit")
@login_required
@admin_required
def audit_log():
    """Read-only: there is deliberately no route that edits or deletes
    audit entries."""

    action = request.args.get("action", "")
    actions = audit_service.list_actions()

    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1

    return render_template(
        "admin/audit.html",
        pagination=audit_service.list_entries(action=action if action in actions else None, page=page),
        actions=actions,
        action=action if action in actions else "",
        parse_details=audit_service.parse_details,
    )
