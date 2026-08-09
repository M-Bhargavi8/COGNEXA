from datetime import datetime
from gaminghub.database.database import db


class GameResult(db.Model):
    __tablename__ = "game_results"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"), nullable=False, index=True)
    game_session_id = db.Column(db.Integer, db.ForeignKey("game_sessions.id"), nullable=False)

    difficulty = db.Column(db.String(20))
    result = db.Column(db.String(10), nullable=False)

    score = db.Column(db.Integer, default=0)
    xp_earned = db.Column(db.Integer, default=0)
    coins_earned = db.Column(db.Integer, default=0)

    duration = db.Column(db.Float)
    attempts = db.Column(db.Integer)
    accuracy = db.Column(db.Float)
    reaction_time = db.Column(db.Float)
    mistakes = db.Column(db.Integer)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<GameResult {self.id} user={self.user_id} game={self.game_id} result={self.result}>"
