from datetime import datetime
from gaminghub.database.database import db


class UserInventory(db.Model):
    __tablename__ = "user_inventory"
    __table_args__ = (
        db.UniqueConstraint("user_id", "shop_item_id", name="uq_user_shop_item"),
    )

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    shop_item_id = db.Column(db.Integer, db.ForeignKey("shop_items.id"), nullable=False, index=True)

    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<UserInventory user={self.user_id} item={self.shop_item_id}>"
