"""Create the catalog products table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_catalog_products"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("price > 0", name="ck_products_price_positive"),
        sa.CheckConstraint(
            "length(btrim(name)) BETWEEN 1 AND 200", name="ck_products_name_length"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        schema="catalog",
    )
    op.create_index(
        "ix_products_created_at_id",
        "products",
        ["created_at", "id"],
        unique=False,
        schema="catalog",
    )


def downgrade() -> None:
    op.drop_index("ix_products_created_at_id", table_name="products", schema="catalog")
    op.drop_table("products", schema="catalog")
