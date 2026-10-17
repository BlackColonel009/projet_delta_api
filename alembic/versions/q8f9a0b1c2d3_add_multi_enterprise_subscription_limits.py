"""add multi-enterprise subscription limits

Revision ID: q8f9a0b1c2d3
Revises: p7e8f9a0b1c2
Create Date: 2026-10-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "q8f9a0b1c2d3"
down_revision: Union[str, None] = "p7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _append_feature(plan_code: str, feature: str) -> None:
    op.execute(
        sa.text(
            "UPDATE subscription_plans "
            "SET features = CASE "
            "WHEN features::jsonb @> CAST(:feature_json AS jsonb) THEN features::jsonb "
            "ELSE features::jsonb || CAST(:feature_json AS jsonb) END "
            "WHERE code = :plan_code"
        ).bindparams(
            feature_json=f'["{feature}"]',
            plan_code=plan_code,
        )
    )


def upgrade() -> None:
    op.add_column(
        "subscription_plans",
        sa.Column("max_enterprises", sa.Integer(), nullable=True),
    )
    op.execute(
        "UPDATE subscription_plans SET max_enterprises = CASE "
        "WHEN code IN ('bronze_free', 'bronze_classic') THEN 1 "
        "WHEN code = 'gold' THEN 3 "
        "ELSE NULL END"
    )
    for plan_code in ("gold", "diamond_pro"):
        _append_feature(plan_code, "multi_enterprise")
        _append_feature(plan_code, "group_dashboard")
        _append_feature(plan_code, "global_stock_search")


def downgrade() -> None:
    for feature in (
        "multi_enterprise",
        "group_dashboard",
        "global_stock_search",
    ):
        op.execute(
            sa.text(
                "UPDATE subscription_plans "
                "SET features = ("
                "SELECT COALESCE(jsonb_agg(value), '[]'::jsonb) "
                "FROM jsonb_array_elements(features::jsonb) value "
                "WHERE value <> to_jsonb(CAST(:feature AS text))"
                ") WHERE code IN ('gold', 'diamond_pro')"
            ).bindparams(feature=feature)
        )
    op.drop_column("subscription_plans", "max_enterprises")
