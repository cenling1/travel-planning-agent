"""Add user-owned knowledge documents and long-term memories."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_user_memory_docs"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_documents") as batch:
        batch.add_column(
            sa.Column(
                "owner_id",
                sa.String(64),
                nullable=False,
                server_default="local",
            )
        )
        batch.drop_constraint("uq_document_filename_hash", type_="unique")
        batch.create_unique_constraint(
            "uq_document_owner_filename_hash",
            ["owner_id", "filename", "content_hash"],
        )
        batch.create_index("ix_knowledge_documents_owner_id", ["owner_id"])

    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("knowledge_documents", "owner_id", server_default=None)

    op.create_table(
        "user_memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("memory_key", sa.String(120), nullable=False),
        sa.Column("memory_type", sa.String(40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("memory_metadata", sa.JSON(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "memory_key", name="uq_user_memory_key"),
    )
    op.create_index("ix_user_memories_owner_id", "user_memories", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_user_memories_owner_id", table_name="user_memories")
    op.drop_table("user_memories")

    with op.batch_alter_table("knowledge_documents") as batch:
        batch.drop_index("ix_knowledge_documents_owner_id")
        batch.drop_constraint("uq_document_owner_filename_hash", type_="unique")
        batch.create_unique_constraint(
            "uq_document_filename_hash",
            ["filename", "content_hash"],
        )
        batch.drop_column("owner_id")
