from flask import Blueprint, g, jsonify, request

from gaminghub.database.database import bcrypt, limiter
from gaminghub.models.user import User
from gaminghub.models.game import Game
from gaminghub.models.game_result import GameResult
from gaminghub.models.achievement import Achievement
from gaminghub.services import (
    api_auth_service,
    leaderboard_service,
    analytics_service,
    notification_service,
    shop_service,
    reward_service,
)
from gaminghub.utils.decorators import api_token_required

api = Blueprint("api", __name__, url_prefix="/api")


# ---------------------------------------------------------------- helpers

def _clamp_limit(raw, default=20, maximum=100):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, min(value, maximum))


def _serialize_game(game):
    return {
        "id": game.id, "name": game.name, "slug": game.slug,
        "description": game.description, "category": game.category,
        "icon": game.icon, "is_active": game.is_active
    }


def _serialize_user_public(user):
    """Public-safe fields only -- no email, no password hash."""
    return {"id": user.id, "username": user.username, "level": user.level}


def _serialize_me(user):
    return {
        "id": user.id, "username": user.username, "email": user.email,
        "role": user.role, "level": user.level, "xp": user.xp, "coins": user.coins,
        "games_played": user.games_played, "wins": user.wins, "losses": user.losses,
        "high_score": user.high_score, "daily_streak": user.daily_streak,
        "avatar": user.avatar, "equipped_frame": user.equipped_frame,
        "equipped_badge": user.equipped_badge,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }


def _serialize_leaderboard_entry(entry):
    return {"rank": entry["rank"], "user": _serialize_user_public(entry["user"]), "value": entry["value"]}


def _serialize_result(result):
    return {
        "id": result.id, "game_id": result.game_id, "difficulty": result.difficulty,
        "result": result.result, "score": result.score, "xp_earned": result.xp_earned,
        "coins_earned": result.coins_earned, "duration": result.duration,
        "attempts": result.attempts, "accuracy": result.accuracy,
        "reaction_time": result.reaction_time, "mistakes": result.mistakes,
        "created_at": result.created_at.isoformat() if result.created_at else None
    }


def _serialize_achievement(achievement):
    return {
        "id": achievement.id, "name": achievement.name, "title": achievement.title,
        "description": achievement.description, "badge": achievement.badge,
        "xp_reward": achievement.xp_reward, "coin_reward": achievement.coin_reward
    }


def _serialize_shop_item(item):
    return {
        "id": item.id, "name": item.name, "description": item.description,
        "item_type": item.item_type, "cost": item.cost, "asset": item.asset
    }


def _serialize_notification(n):
    return {
        "id": n.id, "type": n.type, "icon": n.icon, "title": n.title,
        "message": n.message, "link": n.link, "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None
    }


# ------------------------------------------------------------------- root

@api.route("/")
def api_root():
    return jsonify({
        "name": "Gaming Hub API",
        "version": "1.0",
        "authentication": "POST /api/auth/token with JSON {email, password} to get a token, "
                           "then send 'Authorization: Bearer <token>' on every other request.",
        "endpoints": {
            "auth": ["POST /api/auth/token", "DELETE /api/auth/token"],
            "games": ["GET /api/games", "GET /api/games/<slug>"],
            "leaderboard": [
                "GET /api/leaderboard/global", "GET /api/leaderboard/daily",
                "GET /api/leaderboard/weekly", "GET /api/leaderboard/game/<slug>",
                "GET /api/leaderboard/category/<category>"
            ],
            "achievements": ["GET /api/achievements"],
            "shop": ["GET /api/shop", "POST /api/me/shop/buy/<item_id>"],
            "me": [
                "GET /api/me", "GET /api/me/results", "GET /api/me/achievements",
                "GET /api/me/analytics", "GET /api/me/notifications",
                "POST /api/me/notifications/<id>/read", "POST /api/me/notifications/read-all",
                "POST /api/me/daily-claim"
            ]
        }
    })


# ------------------------------------------------------------------- auth

@api.route("/auth/token", methods=["POST"])
@limiter.limit("10 per minute")
def issue_token():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()

    if not user or not bcrypt.check_password_hash(user.password, password):
        return jsonify({"error": "Invalid email or password."}), 401

    token = api_auth_service.issue_token(user)

    return jsonify({
        "token": token,
        "note": "This token is shown once and can't be retrieved again -- store it securely.",
        "user": _serialize_me(user)
    }), 201


@api.route("/auth/token", methods=["DELETE"])
@api_token_required
def revoke_token():
    api_auth_service.revoke_token(g.api_token)
    return "", 204


# ------------------------------------------------------------------ games

@api.route("/games")
@api_token_required
def list_games():
    games = Game.query.filter_by(is_active=True).order_by(Game.category, Game.name).all()
    return jsonify({"games": [_serialize_game(g_) for g_ in games]})


@api.route("/games/<slug>")
@api_token_required
def get_game(slug):
    game = Game.query.filter_by(slug=slug, is_active=True).first()

    if not game:
        return jsonify({"error": "Game not found."}), 404

    return jsonify({"game": _serialize_game(game)})


# ------------------------------------------------------------- leaderboard

@api.route("/leaderboard/global")
@api_token_required
def leaderboard_global():
    entries = leaderboard_service.get_global_leaderboard(_clamp_limit(request.args.get("limit")))
    return jsonify({"entries": [_serialize_leaderboard_entry(e) for e in entries]})


@api.route("/leaderboard/daily")
@api_token_required
def leaderboard_daily():
    entries = leaderboard_service.get_period_leaderboard("daily", _clamp_limit(request.args.get("limit")))
    return jsonify({"entries": [_serialize_leaderboard_entry(e) for e in entries]})


@api.route("/leaderboard/weekly")
@api_token_required
def leaderboard_weekly():
    entries = leaderboard_service.get_period_leaderboard("weekly", _clamp_limit(request.args.get("limit")))
    return jsonify({"entries": [_serialize_leaderboard_entry(e) for e in entries]})


@api.route("/leaderboard/game/<slug>")
@api_token_required
def leaderboard_game(slug):
    game = Game.query.filter_by(slug=slug).first()

    if not game:
        return jsonify({"error": "Game not found."}), 404

    entries = leaderboard_service.get_game_leaderboard(game, _clamp_limit(request.args.get("limit")))
    return jsonify({"entries": [_serialize_leaderboard_entry(e) for e in entries]})


@api.route("/leaderboard/category/<category>")
@api_token_required
def leaderboard_category(category):
    valid_categories = {c for (c,) in Game.query.with_entities(Game.category).distinct().all()}

    if category not in valid_categories:
        return jsonify({"error": "Unknown category."}), 404

    entries = leaderboard_service.get_category_leaderboard(category, _clamp_limit(request.args.get("limit")))
    return jsonify({"entries": [_serialize_leaderboard_entry(e) for e in entries]})


# ----------------------------------------------------------- achievements

@api.route("/achievements")
@api_token_required
def list_achievements():
    achievements = Achievement.query.order_by(Achievement.id).all()
    return jsonify({"achievements": [_serialize_achievement(a) for a in achievements]})


# ------------------------------------------------------------------- shop

@api.route("/shop")
@api_token_required
def list_shop_items():
    items = shop_service.get_shop_items()
    return jsonify({"items": [_serialize_shop_item(i) for i in items]})


@api.route("/me/shop/buy/<int:item_id>", methods=["POST"])
@api_token_required
def buy_shop_item(item_id):
    success, message = shop_service.purchase_item(g.api_user, item_id)

    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"message": message, "user": _serialize_me(g.api_user)})


# -------------------------------------------------------------------- me

@api.route("/me")
@api_token_required
def me():
    return jsonify({"user": _serialize_me(g.api_user)})


@api.route("/me/results")
@api_token_required
def me_results():
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    per_page = _clamp_limit(request.args.get("per_page"))

    pagination = GameResult.query.filter_by(user_id=g.api_user.id) \
        .order_by(GameResult.created_at.desc()) \
        .paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "results": [_serialize_result(r) for r in pagination.items],
        "page": pagination.page,
        "per_page": per_page,
        "total": pagination.total,
        "pages": pagination.pages
    })


@api.route("/me/achievements")
@api_token_required
def me_achievements():
    return jsonify({"achievements": [_serialize_achievement(a) for a in g.api_user.achievements]})


@api.route("/me/analytics")
@api_token_required
def me_analytics():
    user = g.api_user

    return jsonify({
        "overview": analytics_service.get_overview(user),
        "activity": analytics_service.get_activity_over_time(user),
        "per_game": analytics_service.get_per_game_breakdown(user),
        "skill_profile": analytics_service.get_skill_profile(user),
        "recommendations": [
            {"game": _serialize_game(r["game"]), "reason": r["reason"], "url": r["url"]}
            for r in analytics_service.get_recommendations(user)
        ]
    })


@api.route("/me/notifications")
@api_token_required
def me_notifications():
    limit = _clamp_limit(request.args.get("limit"))
    notifications = notification_service.get_recent(g.api_user, limit=limit)

    return jsonify({
        "notifications": [_serialize_notification(n) for n in notifications],
        "unread_count": notification_service.get_unread_count(g.api_user)
    })


@api.route("/me/notifications/<int:notification_id>/read", methods=["POST"])
@api_token_required
def me_notification_read(notification_id):
    notification = notification_service.mark_read(g.api_user, notification_id)

    if not notification:
        return jsonify({"error": "Notification not found."}), 404

    return jsonify({"notification": _serialize_notification(notification)})


@api.route("/me/notifications/read-all", methods=["POST"])
@api_token_required
def me_notifications_read_all():
    notification_service.mark_all_read(g.api_user)
    return jsonify({"unread_count": 0})


@api.route("/me/daily-claim", methods=["POST"])
@api_token_required
def me_daily_claim():
    success, message, reward = reward_service.claim_daily_reward(g.api_user)

    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"message": message, "coins_awarded": reward, "user": _serialize_me(g.api_user)})
