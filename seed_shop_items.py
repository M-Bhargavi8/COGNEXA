from gaminghub.database.database import db
from gaminghub.models.shop_item import ShopItem
from gaminghub import create_app

app = create_app()

# (name, description, item_type, cost, asset)
SHOP_ITEMS = [
    ("Amara", "Unlock this avatar.", "avatar", 50, "avatar2.png"),
    ("Scholar", "Unlock this avatar.", "avatar", 50, "avatar3.png"),
    ("Braids", "Unlock this avatar.", "avatar", 75, "avatar4.png"),
    ("Vivid", "Unlock this avatar.", "avatar", 75, "avatar5.png"),
    ("Professor", "Unlock this avatar.", "avatar", 100, "avatar6.png"),
    ("Bookworm", "Unlock this avatar.", "avatar", 100, "avatar7.png"),
    ("Classic", "Unlock this avatar.", "avatar", 125, "avatar8.png"),
    ("Beats", "Unlock this avatar.", "avatar", 125, "avatar9.png"),
    ("Curly", "Unlock this avatar.", "avatar", 150, "avatar10.png"),
    ("Neon", "Unlock this avatar.", "avatar", 175, "avatar11.png"),
    ("Swagger", "Unlock this avatar.", "avatar", 200, "avatar12.png"),

    ("Bronze Frame", "A simple bronze border for your avatar.", "frame", 100, "frame-bronze"),
    ("Silver Frame", "A cool silver border for your avatar.", "frame", 200, "frame-silver"),
    ("Gold Frame", "A shining gold border for your avatar.", "frame", 400, "frame-gold"),
    ("Neon Frame", "A glowing neon border for your avatar.", "frame", 600, "frame-neon"),
    ("Diamond Frame", "The rarest border, for the truly dedicated.", "frame", 800, "frame-diamond"),

    ("Crown Badge", "Show off with a crown next to your name.", "badge", 150, "crown"),
    ("Fire Badge", "Show off with a fire badge next to your name.", "badge", 150, "fire"),
    ("Star Badge", "Show off with a star badge next to your name.", "badge", 150, "star"),
    ("Lightning Badge", "Show off with a lightning badge next to your name.", "badge", 150, "lightning"),
    ("Target Badge", "Show off with a target badge next to your name.", "badge", 150, "target"),
    ("Diamond Badge", "The rarest badge, for the truly dedicated.", "badge", 300, "diamond"),

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
