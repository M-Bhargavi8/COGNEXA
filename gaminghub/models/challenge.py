from datetime import datetime, date
from gaminghub.database.database import db


class Challenge(db.Model):
    __tablename__ = "challenges"

    id = db.Column(db.Integer, primary_key=True)

    challenge_date = db.Column(db.Date, unique=True, nullable=False, index=True, default=date.today)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"), nullable=False)

    difficulty = db.Column(db.String(20))
    description = db.Column(db.String(255), nullable=False)
    criteria = db.Column(db.Text, nullable=False)

    xp_reward = db.Column(db.Integer, default=0)
    coin_reward = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Challenge {self.challenge_date}>"
