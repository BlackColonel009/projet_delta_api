"""separate enterprise position from business type

Revision ID: x5a6b7c8d9e0
Revises: w4f5a6b7c8d9
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa


revision = "x5a6b7c8d9e0"
down_revision = "w4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "enterprises",
        sa.Column(
            "business_type",
            sa.String(length=40),
            nullable=False,
            server_default="commerce",
        ),
    )
    op.execute(
        """
        UPDATE enterprises
        SET business_type = CASE
            WHEN enterprise_type = 'consigne' THEN 'legacy_consignment'
            ELSE 'commerce'
        END
        """
    )
    op.create_check_constraint(
        "ck_enterprises_business_type",
        "enterprises",
        "business_type IN ('commerce', 'laundry', 'vehicle_rental', "
        "'property_rental', 'legacy_consignment')",
    )


def downgrade():
    op.drop_constraint(
        "ck_enterprises_business_type",
        "enterprises",
        type_="check",
    )
    op.drop_column("enterprises", "business_type")
