"""Add the audit log for administrative actions (backups, course resets).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-22 15:15:22.507979
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

import mes_server.db.types

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this migration."""
    op.create_table(
        "audit_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", mes_server.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("actor", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("action", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_entries")),
    )
    with op.batch_alter_table("audit_entries", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_audit_entries_action"), ["action"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_audit_entries_created_at"), ["created_at"], unique=False
        )


def downgrade() -> None:
    """Revert this migration."""
    with op.batch_alter_table("audit_entries", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_audit_entries_created_at"))
        batch_op.drop_index(batch_op.f("ix_audit_entries_action"))

    op.drop_table("audit_entries")
