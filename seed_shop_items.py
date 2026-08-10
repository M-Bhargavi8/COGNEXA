from gaminghub.database.database import db
from gaminghub.models.shop_item import ShopItem
from gaminghub import create_app

app = create_app()

# (name, description, item_type, cost, asset)
SHOP_ITEMS = [
    ("Avatar 2", "Unlock this avatar.", "avatar", 50, "avatar2.png"),
    ("Avatar 3", "Unlock this avatar.", "avatar", 50, "avatar3.png"),
    ("Avatar 4", "Unlock this avatar.", "avatar", 75, "avatar4.png"),
    ("Avatar 5", "Unlock this avatar.", "avatar", 75, "avatar5.png"),
    ("Avatar 6", "Unlock this avatar.", "avatar", 100, "avatar6.png"),
    ("Avatar 7", "Unlock this avatar.", "avatar", 100, "avatar7.png"),
    ("Avatar 8", "Unlock this avatar.", "avatar", 150, "avatar8.png"),
    ("Avatar 9", "Unlock this avatar.", "avatar", 150, "avatar9.png"),
    ("Avatar 10", "Unlock this avatar.", "avatar", 200, "avatar10.png"),

    ("Bronze Frame", "A simple bronze border for your avatar.", "frame", 100, "frame-bronze"),
    ("Silver Frame", "A cool silver border for your avatar.", "frame", 200, "frame-silver"),
    ("Gold Frame", "A shining gold border for your avatar.", "frame", 400, "frame-gold"),
    ("Neon Frame", "A glowing neon border for your avatar.", "frame", 600, "frame-neon"),
    ("Diamond Frame", "The rarest border, for the truly dedicated.", "frame", 800, "frame-diamond"),

    ("Crown Badge", "Show off with a crown next to your name.", "badge", 150, "👑"),
    ("Fire Badge", "Show off with a fire badge next to your name.", "badge", 150, "🔥"),
    ("Star Badge", "Show off with a star badge next to your name.", "badge", 150, "🌟"),
    ("Lightning Badge", "Show off with a lightning badge next to your name.", "badge", 150, "⚡"),
    ("Target Badge", "Show off with a target badge next to your name.", "badge", 150, "🎯"),
    ("Diamond Badge", "The rarest badge, for the truly dedicated.", "badge", 300, "💎"),

    ("1 Hour XP Boost", "Double XP from everything for 1 hour after purchase.", "booster", 100, None),
]

with app.app_context():
    for name, description, item_type, cost, asset in SHOP_ITEMS:
        if not ShopItem.query.filter_by(name=name).first():
            db.session.add(ShopItem(
                name=name,
                description=description,
                item_type=item_type,
                cost=cost,
                asset=asset
            ))
    db.session.commit()
    print("Shop items seeded.")
