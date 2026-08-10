from flask import Flask
from flask_login import current_user
from config import Config
from gaminghub.database.database import db, bcrypt, login_manager, migrate, csrf

def create_app():
    app = Flask(__name__)

    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

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

    from gaminghub.services import notification_service

    @app.context_processor
    def inject_notifications():
        if current_user.is_authenticated:
            return {
                "nav_unread_count": notification_service.get_unread_count(current_user),
                "nav_recent_notifications": notification_service.get_recent(current_user, limit=6)
            }
        return {"nav_unread_count": 0, "nav_recent_notifications": []}

    return app
