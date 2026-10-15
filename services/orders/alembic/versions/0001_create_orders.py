"""Create the orders table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_orders"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("unit_price > 0", name="ck_orders_unit_price_positive"),
        sa.CheckConstraint("quantity BETWEEN 1 AND 1000000", name="ck_orders_quantity_range"),
        sa.CheckConstraint("total = unit_price * quantity", name="ck_orders_total_matches_items"),
        sa.PrimaryKeyConstraint("id", name="pk_orders"),
        schema="orders",
    )
    op.create_index(
        "ix_orders_created_at_id",
        "orders",
        ["created_at", "id"],
        unique=False,
        schema="orders",
    )


def downgrade() -> None:
    op.drop_index("ix_orders_created_at_id", table_name="orders", schema="orders")
    op.drop_table("orders", schema="orders")
