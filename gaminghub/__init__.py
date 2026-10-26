import logging
import mimetypes

from flask import Flask, jsonify, render_template, request
from flask_login import current_user
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.middleware.proxy_fix import ProxyFix

from config import BaseConfig, get_config
from gaminghub.database.database import db, bcrypt, login_manager, migrate, csrf, limiter
from gaminghub.utils.log_config import configure_logging

# Werkzeug's static file serving derives Content-Type from Python's
# mimetypes module, whose registered extensions come from the OS --
# .webp is missing from that database on at least one dev machine this
# app has run on, so /static/images/*.webp was served as
# application/octet-stream. Registering it explicitly makes the
# Content-Type correct regardless of the host's own mimetypes config.
mimetypes.add_type("image/webp", ".webp")

logger = logging.getLogger(__name__)


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, connection_record):
    """SQLite ships with foreign keys off and a zero busy timeout, so
    two overlapping writes fail instantly with "database is locked".
    Only applies to SQLite connections; other databases are untouched."""

    module = type(dbapi_connection).__module__
    if not module.startswith(("sqlite3", "pysqlite2")):
        return

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


# Inline <script> is not allowed: page scripts live in static/js and pass
# server data through data-* attributes or JSON blocks. 'unsafe-inline'
# remains for style only -- dozens of templates still set style="..."
# (several with server-computed widths), and style injection is far less
# dangerous than script injection. See docs/SECURITY.md.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "img-src 'self' data:; "
    "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none';"
)


def create_app(config_class=None):
    app = Flask(__name__)

    config_class = config_class or get_config()

    # BaseConfig first so a config class only has to set what it changes
    # (the test suite's config is a plain class with a handful of keys).
    app.config.from_object(BaseConfig)
    app.config.from_object(config_class)

    validate = getattr(config_class, "validate", None)
    problems = validate(app.config) if validate else []
    if problems:
        raise RuntimeError(
            "Refusing to start with an unsafe configuration:\n  - " + "\n  - ".join(problems)
        )

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY is not set.")

    configure_logging(app)

    proxies = app.config.get("TRUSTED_PROXY_COUNT", 0)
    if proxies:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies, x_host=proxies, x_port=proxies)

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
    from gaminghub.routes.account import account
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
    from gaminghub.routes.health import health

    # Register Blueprints
    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(account)
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
    app.register_blueprint(health)

    # Token-authenticated API requests have no session cookie, so they
    # can't be forged by a cross-site request the way cookie auth can --
    # CSRF protection doesn't apply here and would just reject every
    # legitimate API call for lacking a CSRF token it has no way to get.
    csrf.exempt(api)

    # A load balancer polls this constantly; it must never be throttled.
    limiter.exempt(health)

    from gaminghub.services import notification_service

    # Every surface that lists games (landing page, hubs, dashboard,
    # analytics) needs the same slug -> play URL lookup. Exposing the
    # one in game_service as a Jinja global keeps that mapping in a
    # single place instead of each route hand-building URLs into its
    # own context, and lets a template link a game it only has a slug
    # for. Returns None for an unknown/unplayable slug, so callers
    # guard with {% if %} the same way the routes already do.
    from gaminghub.services.game_service import get_play_url, guard_inactive_game

    app.jinja_env.globals["play_url"] = get_play_url

    app.before_request(guard_inactive_game)

    from gaminghub.cli import register_cli

    register_cli(app)

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
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

        # Pages and API responses can carry account data; don't let a
        # shared computer's browser cache or an intermediary keep them.
        if not request.path.startswith("/static/") and "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"

        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response

    def _wants_json():
        return request.path.startswith("/api/")

    # A 404 from an unmatched URL happens before Flask ever picks a
    # blueprint, so a blueprint-scoped errorhandler can't catch it --
    # only an app-level one can, hence checking the path prefix here.
    @app.errorhandler(404)
    def handle_404(error):
        if _wants_json():
            return jsonify({"error": "Not found."}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def handle_403(error):
        if _wants_json():
            return jsonify({"error": "Forbidden."}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(405)
    def handle_405(error):
        if _wants_json():
            return jsonify({"error": "Method not allowed."}), 405
        return error

    @app.errorhandler(413)
    def handle_413(error):
        if _wants_json():
            return jsonify({"error": "Request body too large."}), 413
        return error

    @app.errorhandler(429)
    def handle_429(error):
        if _wants_json():
            return jsonify({"error": "Too many requests. Try again later."}), 429
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def handle_500(error):
        # Flask has already logged the traceback; the response never
        # includes it, whatever the environment.
        if _wants_json():
            return jsonify({"error": "Internal server error."}), 500
        # errors/500.html deliberately doesn't extend base.html: if this
        # fired because the database is unreachable, base.html's nav
        # (which queries notifications for current_user) would just
        # fail again while rendering the error page itself.
        return render_template("errors/500.html"), 500

    return app
