from flask import Blueprint, render_template
from flask_login import login_required

from gaminghub.services import game_service
from gaminghub.models.game import Game

brain_lab = Blueprint("brain_lab", __name__, url_prefix="/brain-lab")


def outcome_extras(outcome):
    """JSON-serializable achievements/challenge info from a complete_session() result."""

    challenge = outcome.get("challenge_completed")

    return {
        "achievements_unlocked": [
            {"title": a.title, "badge": a.badge}
            for a in outcome.get("achievements_unlocked", [])
        ],
        "challenge_completed": {
            "description": challenge.description,
            "xp": challenge.xp_reward,
            "coins": challenge.coin_reward
        } if challenge else None
    }


@brain_lab.route("/")
@login_required
def hub():

    games = Game.query.filter_by(
        category="brain-lab",
        is_active=True
    ).all()

    game_cards = [
        {"game": g, "url": game_service.get_play_url(g.slug)}
        for g in games
    ]

    game_cards = [c for c in game_cards if c["url"]]

    return render_template("brain_lab/hub.html", game_cards=game_cards)


# Each submodule attaches its routes to the `brain_lab` blueprint defined
# above via `from gaminghub.routes.brain_lab import brain_lab`. Importing
# them here (after the blueprint exists) is what actually registers those
# routes -- add new games to this list.
from gaminghub.routes.brain_lab import memory_matrix  # noqa: E402,F401
from gaminghub.routes.brain_lab import reflex_lab  # noqa: E402,F401
from gaminghub.routes.brain_lab import focus_shift  # noqa: E402,F401
from gaminghub.routes.brain_lab import sequence_breaker  # noqa: E402,F401
from gaminghub.routes.brain_lab import code_breaker  # noqa: E402,F401
from gaminghub.routes.brain_lab import dual_task  # noqa: E402,F401
from gaminghub.routes.brain_lab import risk_reward  # noqa: E402,F401
from gaminghub.routes.brain_lab import logic_grid  # noqa: E402,F401
