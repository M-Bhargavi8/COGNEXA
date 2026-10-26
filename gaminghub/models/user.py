from datetime import datetime
from flask_login import UserMixin
from gaminghub.database.database import db


# Account status values. Only "active" accounts can sign in or use the
# API; the others keep every row (results, purchases, achievements) so
# history and leaderboards stay consistent -- nothing is hard-deleted.
STATUS_ACTIVE = "active"
STATUS_SUSPENDED = "suspended"
STATUS_DEACTIVATED = "deactivated"
ACCOUNT_STATUSES = (STATUS_ACTIVE, STATUS_SUSPENDED, STATUS_DEACTIVATED)


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="player", nullable=False)

    coins = db.Column(db.Integer, default=100)
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)

    games_played = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    high_score = db.Column(db.Integer, default=0)

    bio = db.Column(db.String(300), default="I love strategy games.")
    country = db.Column(db.String(50), default="India")
    favorite_game = db.Column(db.String(100), default="Guess The Number")
    avatar = db.Column(db.String(200), default="avatar1.png")
    title = db.Column(db.String(100), default="Beginner")

    equipped_frame = db.Column(db.String(50))
    equipped_badge = db.Column(db.String(10))
    xp_booster_expires_at = db.Column(db.DateTime)

    login_streak = db.Column(db.Integer, default=1)
    daily_streak = db.Column(db.Integer, default=0)
    last_claim = db.Column(db.Date)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # NULL until the address is proven by a verification link -- never
    # set any other way (accounts created before verification existed
    # simply stay unverified until they verify).
    email_verified_at = db.Column(db.DateTime)

    status = db.Column(db.String(20), default=STATUS_ACTIVE, server_default=STATUS_ACTIVE, nullable=False, index=True)
    status_reason = db.Column(db.String(255))
    status_changed_at = db.Column(db.DateTime)

    # Bumped whenever existing sign-ins must stop working (password
    # change/reset, suspension). It's part of get_id(), so session and
    # remember-me cookies minted before the bump no longer resolve.
    auth_version = db.Column(db.Integer, default=0, server_default="0", nullable=False)
    password_changed_at = db.Column(db.DateTime)

    def __repr__(self):
        return f"<User {self.username}>"

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_active(self):
        # Flask-Login consults this: login_user() refuses inactive users.
        return self.status == STATUS_ACTIVE

    @property
    def is_email_verified(self):
        return self.email_verified_at is not None

    def get_id(self):
        return f"{self.id}:{self.auth_version or 0}"

    achievements = db.relationship(
    "Achievement",
    secondary="user_achievements",
    backref="users",
    lazy=True
)
