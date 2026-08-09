from datetime import datetime
from gaminghub.database.database import db


class GameSession(db.Model):
    __tablename__ = "game_sessions"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"), nullable=False, index=True)

    difficulty = db.Column(db.String(20))
    state = db.Column(db.Text, default="{}", nullable=False)
    status = db.Column(db.String(20), default="active", nullable=False, index=True)
    session_token = db.Column(db.String(64))

    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)

    def __repr__(self):
        return f"<GameSession {self.id} user={self.user_id} game={self.game_id} status={self.status}>"
