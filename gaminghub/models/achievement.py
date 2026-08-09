'''from gaminghub.database.database import db

class Achievement(db.Model):

    __tablename__ = "achievements"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), unique=True, nullable=False)

    description = db.Column(db.String(200))

    icon = db.Column(db.String(100))

    xp_reward = db.Column(db.Integer, default=0)

    coin_reward = db.Column(db.Integer, default=0)'''

from gaminghub.database.database import db


class Achievement(db.Model):
    __tablename__ = "achievements"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)   # used for lookup in unlock()
    title = db.Column(db.String(100), nullable=False)               # shown on dashboard
    description = db.Column(db.String(255))
    badge = db.Column(db.String(10))                                # emoji icon
    coin_reward = db.Column(db.Integer, default=0)
    xp_reward = db.Column(db.Integer, default=0)
    
    