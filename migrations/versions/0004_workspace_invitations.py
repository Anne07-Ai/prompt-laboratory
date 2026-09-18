"""Add workspace invitations.

Revision ID: 0004
Revises: 0003
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

ROLES = ("admin", "editor", "viewer")
STATUSES = ("pending", "accepted", "rejected", "revoked", "expired")


def upgrade() -> None:
    op.create_table(
        "workspace_invitations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("inviter_user_id", sa.String(length=36), nullable=False),
        sa.Column("invited_email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            f"role IN ({', '.join(repr(role) for role in ROLES)})",
            name="ck_workspace_invitations_role",
        ),
        sa.CheckConstraint(
            f"status IN ({', '.join(repr(status) for status in STATUSES)})",
            name="ck_workspace_invitations_status",
        ),
        sa.ForeignKeyConstraint(
            ["inviter_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_workspace_invitations_workspace_id",
        "workspace_invitations",
        ["workspace_id"],
    )
    op.create_index(
        "ix_workspace_invitations_invited_email",
        "workspace_invitations",
        ["invited_email"],
    )


def downgrade() -> None:
    op.drop_table("workspace_invitations")
