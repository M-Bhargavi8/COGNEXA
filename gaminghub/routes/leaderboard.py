from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user

from gaminghub.services import leaderboard_service
from gaminghub.services.game_service import get_game
from gaminghub.models.game import Game

leaderboard = Blueprint("leaderboard", __name__)


CATEGORY_LABELS = {
    "classic-arcade": "Classic Arcade",
    "brain-lab": "Brain Lab",
}


def _picker_context():
    games = Game.query.filter_by(is_active=True).order_by(Game.category, Game.name).all()
    categories = [
        c for (c,) in Game.query.with_entities(Game.category).distinct().order_by(Game.category).all()
    ]
    return games, categories


def _render(view, title, value_label, entries, my_rank, my_value, **extra):
    games, categories = _picker_context()

    return render_template(
        "leaderboard.html",
        view=view,
        title=title,
        value_label=value_label,
        entries=entries,
        my_rank=my_rank,
        my_value=my_value,
        games=games,
        categories=categories,
        category_labels=CATEGORY_LABELS,
        **extra
    )


@leaderboard.route("/leaderboard")
@login_required
def leaderboard_home():
    return _render(
        "global", "Global Leaderboard", "Total XP",
        leaderboard_service.get_global_leaderboard(),
        leaderboard_service.get_my_global_rank(current_user),
        None
    )


@leaderboard.route("/leaderboard/daily")
@login_required
def daily():
    my_rank, my_value = leaderboard_service.get_my_period_rank(current_user, "daily")

    return _render(
        "daily", "Daily Leaderboard", "XP Today",
        leaderboard_service.get_period_leaderboard("daily"),
        my_rank, my_value
    )


@leaderboard.route("/leaderboard/weekly")
@login_required
def weekly():
    my_rank, my_value = leaderboard_service.get_my_period_rank(current_user, "weekly")

    return _render(
        "weekly", "Weekly Leaderboard", "XP This Week",
        leaderboard_service.get_period_leaderboard("weekly"),
        my_rank, my_value
    )


@leaderboard.route("/leaderboard/game/<slug>")
@login_required
def by_game(slug):
    game = get_game(slug)

    if not game:
        abort(404)

    my_rank, my_value = leaderboard_service.get_my_game_rank(current_user, game)

    return _render(
        "game", f"{game.icon} {game.name} Leaderboard", "Best Score",
        leaderboard_service.get_game_leaderboard(game),
        my_rank, my_value,
        current_game=game
    )


@leaderboard.route("/leaderboard/category/<category>")
@login_required
def by_category(category):
    _, categories = _picker_context()

    if category not in categories:
        abort(404)

    my_rank, my_value = leaderboard_service.get_my_category_rank(current_user, category)

    return _render(
        "category", f"{CATEGORY_LABELS.get(category, category)} Leaderboard", "Total Score",
        leaderboard_service.get_category_leaderboard(category),
        my_rank, my_value,
        current_category=category
    )
