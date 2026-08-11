from flask import Flask, jsonify, request
from flask_login import current_user
from config import Config
from gaminghub.database.database import db, bcrypt, login_manager, migrate, csrf, limiter

def create_app(config_class=Config):
    app = Flask(__name__)

    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

    # Import models so SQLAlchemy/Alembic can see all tables
    from gaminghub import models

    # Import Blueprints
    from gaminghub.routes.main import main
    from gaminghub.routes.auth import auth
    from gaminghub.routes.admin import admin
    from gaminghub.routes.games import games
    from gaminghub.routes.dashboard import dashboard
    from gaminghub.routes.leaderboard import leaderboard
    from gaminghub.routes.profile import profile
    from gaminghub.routes.gamehub import gamehub
    from gaminghub.routes.tictactoe import tictactoe
    from gaminghub.routes.rewards import rewards
    from gaminghub.routes.brain_lab import brain_lab
    from gaminghub.routes.analytics import analytics
    from gaminghub.routes.notifications import notifications
    from gaminghub.routes.api import api

    # Register Blueprints
    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(admin)
    app.register_blueprint(games)
    app.register_blueprint(dashboard)
    app.register_blueprint(leaderboard)
    app.register_blueprint(tictactoe)
    app.register_blueprint(gamehub)
    app.register_blueprint(profile)
    app.register_blueprint(rewards)
    app.register_blueprint(brain_lab)
    app.register_blueprint(analytics)
    app.register_blueprint(notifications)
    app.register_blueprint(api)

    # Token-authenticated API requests have no session cookie, so they
    # can't be forged by a cross-site request the way cookie auth can --
    # CSRF protection doesn't apply here and would just reject every
    # legitimate API call for lacking a CSRF token it has no way to get.
    csrf.exempt(api)

    from gaminghub.services import notification_service

    @app.context_processor
    def inject_notifications():
        if current_user.is_authenticated:
            return {
                "nav_unread_count": notification_service.get_unread_count(current_user),
                "nav_recent_notifications": notification_service.get_recent(current_user, limit=6)
            }
        return {"nav_unread_count": 0, "nav_recent_notifications": []}

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 'unsafe-inline' is needed for both script-src and style-src because
        # several templates (rps.html, guessing.html, dashboard.html's xp bar
        # width, ...) use inline <script>/style= today. This still blocks the
        # more severe case -- loading a script/stylesheet from an attacker-
        # controlled external host -- which is the main thing CSP buys here.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )

        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response

    # A 404 from an unmatched URL happens before Flask ever picks a
    # blueprint, so a blueprint-scoped errorhandler can't catch it --
    # only an app-level one can, hence checking the path prefix here.
    @app.errorhandler(404)
    def handle_404(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found."}), 404
        return error

    @app.errorhandler(500)
    def handle_500(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error."}), 500
        return error

    return app
