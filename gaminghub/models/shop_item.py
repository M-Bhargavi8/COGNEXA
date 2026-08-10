from datetime import datetime
from gaminghub.database.database import db


class ShopItem(db.Model):
    __tablename__ = "shop_items"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    item_type = db.Column(db.String(20), nullable=False)  # avatar | frame | badge | booster
    cost = db.Column(db.Integer, nullable=False, default=0)

    # avatar: image filename in static/images/avatars/
    # frame: CSS class name applied around the avatar
    # badge: an emoji shown next to the username
    # booster: unused, the effect is fixed (see shop_service)
    asset = db.Column(db.String(200))

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ShopItem {self.item_type}:{self.name}>"
