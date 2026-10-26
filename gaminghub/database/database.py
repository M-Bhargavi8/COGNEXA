from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per hour"])


login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    """
    user_id is what User.get_id() produced: "<id>:<auth_version>". A
    session minted before the account's auth_version was bumped
    (password change/reset, suspension) no longer matches and is treated
    as signed out. A bare "<id>" -- sessions created before auth_version
    existed -- is honoured only while the version is still 0, so
    deploying this doesn't sign everyone out.
    """

    from gaminghub.models.user import User

    raw_id, _, version = str(user_id).partition(":")

    try:
        user = db.session.get(User, int(raw_id))
        version = int(version) if version else None
    except (TypeError, ValueError):
        return None

    if user is None or not user.is_active:
        return None

    if (version if version is not None else 0) != (user.auth_version or 0):
        return None

    return user
