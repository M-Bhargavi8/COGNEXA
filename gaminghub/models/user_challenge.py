from datetime import datetime
from gaminghub.database.database import db


class UserChallenge(db.Model):
    __tablename__ = "user_challenges"
    __table_args__ = (
        db.UniqueConstraint("user_id", "challenge_id", name="uq_user_challenge"),
    )

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenges.id"), nullable=False, index=True)
    game_result_id = db.Column(db.Integer, db.ForeignKey("game_results.id"))

    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<UserChallenge user={self.user_id} challenge={self.challenge_id}>"
