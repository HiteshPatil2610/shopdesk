"""pricing: SP "…10 → …00" switch (owner's rule, 2026-10-04)

Revision ID: 0004_sp_avoid_ten
Revises: 0003_catalog_pricing
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_sp_avoid_ten"
down_revision = "0003_catalog_pricing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pricing_settings",
        sa.Column("sp_avoid_ten", sa.Boolean(), server_default=sa.true(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("pricing_settings", "sp_avoid_ten")
