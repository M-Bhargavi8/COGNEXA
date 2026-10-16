"""create the base users table

The first migrations alter a `users` table that db.create_all() originally
made outside Alembic, so `flask db upgrade` on an empty database failed with
NoSuchTableError. This migration creates that table exactly as it stood
before 89dfbd636ba6, which then adds `bio` and drops `avatar`.

Databases that already exist are past this point in the chain, so they never
run it.

Revision ID: 1f0c9a7e3b21
Revises:
Create Date: 2026-10-16 12:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1f0c9a7e3b21'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=50), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('password', sa.String(length=255), nullable=False),
    sa.Column('coins', sa.Integer(), nullable=True),
    sa.Column('xp', sa.Integer(), nullable=True),
    sa.Column('level', sa.Integer(), nullable=True),
    sa.Column('games_played', sa.Integer(), nullable=True),
    sa.Column('wins', sa.Integer(), nullable=True),
    sa.Column('losses', sa.Integer(), nullable=True),
    sa.Column('high_score', sa.Integer(), nullable=True),
    sa.Column('avatar', sa.String(length=200), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )


def downgrade():
    op.drop_table('users')
