"""cosmetic badge emoji to slugs

Shop badges stored the emoji itself in shop_items.asset, and equipping
one copied that emoji into users.equipped_badge. The player portal now
renders badges from the SVG icon set, which needs a stable key rather
than a glyph, so both columns move to slugs.

Unlike games and achievements -- where the emoji sat alongside a `slug`
/ `name` column that could be keyed off without touching data -- here
the glyph WAS the value, so there is nothing else to look up by.

Revision ID: d3f8b2c15a07
Revises: c7a1e9d40f21
Create Date: 2026-08-15

"""
import sqlalchemy as sa
from alembic import op


revision = "d3f8b2c15a07"
down_revision = "c7a1e9d40f21"
branch_labels = None
depends_on = None


BADGES = [
    ("\N{CROWN}", "crown"),
    ("\N{FIRE}", "fire"),
    ("\N{GLOWING STAR}", "star"),
    ("\N{HIGH VOLTAGE SIGN}", "lightning"),
    ("\N{DIRECT HIT}", "target"),
    ("\N{GEM STONE}", "diamond"),
]


def _rewrite(pairs):
    connection = op.get_bind()

    for source, target in pairs:
        # Scoped to badge rows: frame assets are CSS class names and
        # avatar assets are filenames, neither of which should change.
        connection.execute(
            sa.text(
                "UPDATE shop_items SET asset = :target "
                "WHERE item_type = 'badge' AND asset = :source"
            ),
            {"target": target, "source": source},
        )
        connection.execute(
            sa.text("UPDATE users SET equipped_badge = :target WHERE equipped_badge = :source"),
            {"target": target, "source": source},
        )


def upgrade():
    _rewrite(BADGES)


def downgrade():
    _rewrite([(slug, emoji) for emoji, slug in BADGES])
