from flask import Blueprint, render_template
from flask_login import current_user

from gaminghub.database.database import db
from gaminghub.models.game import Game
from gaminghub.models.achievement import Achievement
from gaminghub.services import (
    analytics_service,
    challenge_service,
    game_service,
    leaderboard_service,
)
from gaminghub.utils.radar import build_radar

main = Blueprint("main", __name__)

@main.route("/")
def home():
    brain_lab_games = Game.query.filter_by(
        category="brain-lab",
        is_active=True
    ).order_by(Game.name).limit(4).all()

    casual_games = Game.query.filter_by(
        category="classic-arcade",
        is_active=True
    ).order_by(Game.name).all()

    total_games = Game.query.filter_by(is_active=True).count()
    total_achievements = Achievement.query.count()

    showcase_achievements = Achievement.query.order_by(
        Achievement.xp_reward.desc()
    ).limit(6).all()

    top_players = leaderboard_service.get_global_leaderboard(limit=5)

    challenge = challenge_service.get_today_challenge()
    challenge_game = db.session.get(Game, challenge.game_id) if challenge else None

    # The hero chart shows the visitor their own shape where there is
    # one, and the platform average otherwise -- real numbers either
    # way, never a fabricated sample profile. A signed-in player also
    # gets the average drawn behind theirs to compare against.
    platform_profile = analytics_service.get_radar_profile()

    if current_user.is_authenticated:
        hero_radar = build_radar(
            analytics_service.get_radar_profile(current_user),
            compare=platform_profile,
        )
        radar_label = "Your profile"
        radar_compare_label = "Platform average"
    else:
        hero_radar = build_radar(platform_profile)
        radar_label = "Platform average"
        radar_compare_label = None

    return render_template(
        "index.html",
        hero_radar=hero_radar,
        radar_label=radar_label,
        radar_compare_label=radar_compare_label,
        skill_count=len(analytics_service.SKILLS),
        brain_lab_games=brain_lab_games,
        casual_games=casual_games,
        total_games=total_games,
        total_achievements=total_achievements,
        showcase_achievements=showcase_achievements,
        top_players=top_players,
        challenge=challenge,
        challenge_game=challenge_game,
        challenge_url=game_service.get_play_url(challenge_game.slug) if challenge_game else None
    )