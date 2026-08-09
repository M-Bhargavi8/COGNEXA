from datetime import datetime
from gaminghub.database.database import db


class Game(db.Model):
    __tablename__ = "games"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    category = db.Column(db.String(50))
    icon = db.Column(db.String(20))
    thumbnail = db.Column(db.String(200))

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Game {self.slug}>"
