"""move avatars from png to svg

Nine of the ten avatar PNGs shipped as zero-byte files, so every avatar
except the first rendered as a broken image in the shop, the dashboard
and the profile page. They were replaced with SVG, which also drops the
per-avatar file from a few KB to under 1 KB and stays sharp on retina.

Filenames are stored in two places -- users.avatar and the asset column
of the avatar shop items -- so existing rows need rewriting or they
point at files that no longer exist.

Revision ID: c7a1e9d40f21
Revises: bc53245c6948
Create Date: 2026-08-15

"""
from alembic import op


revision = "c7a1e9d40f21"
down_revision = "bc53245c6948"
branch_labels = None
depends_on = None


def upgrade():
    # Scoped to the avatarN.png pattern rather than a blanket replace:
    # shop assets also hold frame class names and badge glyphs, and
    # users.avatar is free text that shouldn't be rewritten wholesale.
    op.execute(
        """
        UPDATE users
           SET avatar = REPLACE(avatar, '.png', '.svg')
         WHERE avatar LIKE 'avatar%.png'
        """
    )
    op.execute(
        """
        UPDATE shop_items
           SET asset = REPLACE(asset, '.png', '.svg')
         WHERE item_type = 'avatar'
           AND asset LIKE 'avatar%.png'
        """
    )


def downgrade():
    op.execute(
        """
        UPDATE users
           SET avatar = REPLACE(avatar, '.svg', '.png')
         WHERE avatar LIKE 'avatar%.svg'
        """
    )
    op.execute(
        """
        UPDATE shop_items
           SET asset = REPLACE(asset, '.svg', '.png')
         WHERE item_type = 'avatar'
           AND asset LIKE 'avatar%.svg'
        """
    )
