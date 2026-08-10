from datetime import datetime
from gaminghub.database.database import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # achievement | level_up | personal_best | challenge | daily_reward | daily_challenge
    type = db.Column(db.String(30), nullable=False)

    icon = db.Column(db.String(10))
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.String(255))
    link = db.Column(db.String(200))  # relative URL, shown as "view" if present

    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<Notification user={self.user_id} type={self.type}>"
