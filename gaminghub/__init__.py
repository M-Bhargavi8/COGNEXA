from flask import Flask
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

    return app
