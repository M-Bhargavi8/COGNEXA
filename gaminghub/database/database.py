from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf import CSRFProtect

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()


login_manager.login_view = "auth.login"

@login_manager.user_loader
def load_user(user_id):
    from gaminghub.models.user import User
    return User.query.get(int(user_id))