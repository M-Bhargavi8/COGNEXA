from gaminghub.database import db


class UserAchievement(db.Model):

    __tablename__ = "user_achievements"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id")
    )

    achievement_id = db.Column(
        db.Integer,
        db.ForeignKey("achievements.id")
    )