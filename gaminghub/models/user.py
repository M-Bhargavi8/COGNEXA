from datetime import datetime
from flask_login import UserMixin
from gaminghub.database.database import db


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
    avatar = db.Column(db.String(200), default="default.png")
    title = db.Column(db.String(100), default="Beginner")

    login_streak = db.Column(db.Integer, default=1)
    daily_streak = db.Column(db.Integer, default=0)
    last_claim = db.Column(db.Date)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    def __repr__(self):
        return f"<User {self.username}>"

    @property
    def is_admin(self):
        return self.role == "admin"

    achievements = db.relationship(
    "Achievement",
    secondary="user_achievements",
    backref="users",
    lazy=True
)