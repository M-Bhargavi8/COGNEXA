"""replace avatar set with real character art

The 10 avatars shipped as either zero-byte files (fixed earlier by
generating abstract SVG placeholders) or, now, real character art the
user supplied -- see gaminghub/templates/_logo.html's sibling comment
in the avatars directory for how the source images were cleaned up
(background-key removal, checkerboard-artifact repair) before being
added here. This retires the SVG placeholder set in favour of the real
one and adds two new avatars (11, 12) the old scheme didn't have.

Existing shop_item rows are updated in place (name/cost/asset) rather
than deleted-and-reinserted, so a row a test user already owns --
user_inventory has a real example, id 1 "Avatar 2" -- keeps its id and
stays owned, just now pointing at the real art under a new name.

Revision ID: e91a4c6f2b83
Revises: d3f8b2c15a07
Create Date: 2026-08-16

"""
import sqlalchemy as sa
from alembic import op


revision = "e91a4c6f2b83"
down_revision = "d3f8b2c15a07"
branch_labels = None
depends_on = None


# old (name, asset) -> new (name, cost, asset), matched by avatar slot
# number rather than by name, since the names themselves are changing.
SLOT_UPDATES = [
    ("Avatar 2",  "Amara",     50,  "avatar2.png"),
    ("Avatar 3",  "Scholar",   50,  "avatar3.png"),
    ("Avatar 4",  "Braids",    75,  "avatar4.png"),
    ("Avatar 5",  "Vivid",     75,  "avatar5.png"),
    ("Avatar 6",  "Professor", 100, "avatar6.png"),
    ("Avatar 7",  "Bookworm",  100, "avatar7.png"),
    ("Avatar 8",  "Classic",   125, "avatar8.png"),
    ("Avatar 9",  "Beats",     125, "avatar9.png"),
    ("Avatar 10", "Curly",     150, "avatar10.png"),
]

NEW_ITEMS = [
    ("Neon",     "Unlock this avatar.", "avatar", 175, "avatar11.png"),
    ("Swagger",  "Unlock this avatar.", "avatar", 200, "avatar12.png"),
]


def upgrade():
    connection = op.get_bind()

    for old_name, new_name, cost, asset in SLOT_UPDATES:
        connection.execute(
            sa.text(
                "UPDATE shop_items SET name = :new_name, cost = :cost, asset = :asset "
                "WHERE item_type = 'avatar' AND name = :old_name"
            ),
            {"new_name": new_name, "cost": cost, "asset": asset, "old_name": old_name},
        )

    # is_active is bound as a Python bool rather than a literal 1: SQLite
    # stores either as 1, but PostgreSQL rejects an integer for a boolean
    # column. (Portability fix -- the result on SQLite is unchanged.)
    for name, description, item_type, cost, asset in NEW_ITEMS:
        connection.execute(
            sa.text(
                "INSERT INTO shop_items (name, description, item_type, cost, asset, is_active) "
                "VALUES (:name, :description, :item_type, :cost, :asset, :is_active)"
            ),
            {"name": name, "description": description, "item_type": item_type,
             "cost": cost, "asset": asset, "is_active": True},
        )

    connection.execute(
        sa.text("UPDATE users SET avatar = 'avatar1.png' WHERE avatar = 'avatar1.svg'")
    )


def downgrade():
    connection = op.get_bind()

    for old_name, new_name, cost, asset in SLOT_UPDATES:
        old_asset = asset.replace(".png", ".svg")
        connection.execute(
            sa.text(
                "UPDATE shop_items SET name = :old_name, asset = :old_asset "
                "WHERE item_type = 'avatar' AND name = :new_name"
            ),
            {"old_name": old_name, "old_asset": old_asset, "new_name": new_name},
        )

    for name, *_ in NEW_ITEMS:
        connection.execute(
            sa.text("DELETE FROM shop_items WHERE item_type = 'avatar' AND name = :name"),
            {"name": name},
        )

    connection.execute(
        sa.text("UPDATE users SET avatar = 'avatar1.svg' WHERE avatar = 'avatar1.png'")
    )
