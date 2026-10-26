"""account security, admin audit log and API token expiry

Adds what account self-service and admin management need:

* users: email verification timestamp, account status (active /
  suspended / deactivated) with reason and timestamp, an auth_version
  counter that invalidates old sessions, and password_changed_at.
  Existing users get status='active' and auth_version=0 through server
  defaults, so every current account keeps working and every existing
  session stays valid. email_verified_at stays NULL for them: nothing
  has proven those addresses, so they are not marked verified.
* account_tokens: hashed, single-use, expiring email tokens.
* audit_logs: append-only record of admin and security actions.
* api_tokens.expires_at: tokens issued before this migration get an
  expiry of API_TOKEN_TTL_DAYS (30) from the moment of the upgrade
  rather than from creation, so no client is cut off without notice.
* indexes on game_results.created_at (daily/weekly leaderboards filter
  on it) and notifications(user_id, is_read) (the unread badge query
  runs on every page view).

Revision ID: a4c2e8f61b90
Revises: e91a4c6f2b83
Create Date: 2026-10-26

"""
from datetime import datetime, timedelta

import sqlalchemy as sa
from alembic import op


revision = "a4c2e8f61b90"
down_revision = "e91a4c6f2b83"
branch_labels = None
depends_on = None


LEGACY_API_TOKEN_TTL_DAYS = 30


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("email_verified_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("status", sa.String(length=20), server_default="active", nullable=False))
        batch_op.add_column(sa.Column("status_reason", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("status_changed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("auth_version", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("password_changed_at", sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f("ix_users_status"), ["status"], unique=False)

    with op.batch_alter_table("api_tokens", schema=None) as batch_op:
        batch_op.add_column(sa.Column("expires_at", sa.DateTime(), nullable=True))

    op.get_bind().execute(
        sa.text("UPDATE api_tokens SET expires_at = :expires WHERE expires_at IS NULL"),
        {"expires": datetime.utcnow() + timedelta(days=LEGACY_API_TOKEN_TTL_DAYS)},
    )

    op.create_table(
        "account_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("account_tokens", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_account_tokens_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_account_tokens_token_hash"), ["token_hash"], unique=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("target_type", sa.String(length=30), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("target_label", sa.String(length=120), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_audit_logs_actor_id"), ["actor_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_audit_logs_action"), ["action"], unique=False)
        batch_op.create_index(batch_op.f("ix_audit_logs_created_at"), ["created_at"], unique=False)

    with op.batch_alter_table("game_results", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_game_results_created_at"), ["created_at"], unique=False)

    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.create_index("ix_notifications_user_id_is_read", ["user_id", "is_read"], unique=False)


def downgrade():
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.drop_index("ix_notifications_user_id_is_read")

    with op.batch_alter_table("game_results", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_game_results_created_at"))

    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_audit_logs_created_at"))
        batch_op.drop_index(batch_op.f("ix_audit_logs_action"))
        batch_op.drop_index(batch_op.f("ix_audit_logs_actor_id"))
    op.drop_table("audit_logs")

    with op.batch_alter_table("account_tokens", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_account_tokens_token_hash"))
        batch_op.drop_index(batch_op.f("ix_account_tokens_user_id"))
    op.drop_table("account_tokens")

    with op.batch_alter_table("api_tokens", schema=None) as batch_op:
        batch_op.drop_column("expires_at")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_status"))
        batch_op.drop_column("password_changed_at")
        batch_op.drop_column("auth_version")
        batch_op.drop_column("status_changed_at")
        batch_op.drop_column("status_reason")
        batch_op.drop_column("status")
        batch_op.drop_column("email_verified_at")
