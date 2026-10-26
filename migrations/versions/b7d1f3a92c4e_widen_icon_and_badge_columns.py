"""widen notifications.icon and users.equipped_badge

notifications.icon was VARCHAR(10) but holds icon slugs such as
"achievement" (11 characters). SQLite ignores declared lengths, so this
never failed in development; PostgreSQL rejects the insert, which would
turn every achievement unlock into a 500. users.equipped_badge (badge
slugs, longest currently 9) is widened at the same time for headroom.

Revision ID: b7d1f3a92c4e
Revises: a4c2e8f61b90
Create Date: 2026-10-26

"""
import sqlalchemy as sa
from alembic import op


revision = "b7d1f3a92c4e"
down_revision = "a4c2e8f61b90"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.alter_column("icon", existing_type=sa.String(length=10), type_=sa.String(length=30), existing_nullable=True)

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("equipped_badge", existing_type=sa.String(length=10), type_=sa.String(length=30), existing_nullable=True)


def downgrade():
    # Values longer than 10 characters would not fit back; trim them
    # first so the downgrade can't fail halfway on PostgreSQL.
    op.execute("UPDATE notifications SET icon = SUBSTR(icon, 1, 10) WHERE LENGTH(icon) > 10")
    op.execute("UPDATE users SET equipped_badge = SUBSTR(equipped_badge, 1, 10) WHERE LENGTH(equipped_badge) > 10")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("equipped_badge", existing_type=sa.String(length=30), type_=sa.String(length=10), existing_nullable=True)

    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.alter_column("icon", existing_type=sa.String(length=30), type_=sa.String(length=10), existing_nullable=True)
