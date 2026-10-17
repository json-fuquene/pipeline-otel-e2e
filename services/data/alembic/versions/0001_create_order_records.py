"""Create the data-service order_records table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_data_order_records"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "order_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity BETWEEN 1 AND 1000000", name="ck_order_records_quantity_range"),
        sa.CheckConstraint("total > 0", name="ck_order_records_total_positive"),
        sa.PrimaryKeyConstraint("id", name="pk_order_records"),
        sa.UniqueConstraint("order_id", name="uq_order_records_order_id"),
        schema="data",
    )
    op.create_index(
        "ix_order_records_recorded_at", "order_records", ["recorded_at"], unique=False, schema="data"
    )


def downgrade() -> None:
    op.drop_index("ix_order_records_recorded_at", table_name="order_records", schema="data")
    op.drop_table("order_records", schema="data")
