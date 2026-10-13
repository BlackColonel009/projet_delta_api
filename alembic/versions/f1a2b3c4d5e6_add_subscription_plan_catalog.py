"""add subscription plan catalog

Revision ID: f1a2b3c4d5e6
Revises: f0a1b2c3d4e5
Create Date: 2026-10-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscription_plans",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("monthly_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("annual_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="XOF"),
        sa.Column("max_sub_users", sa.Integer(), nullable=True),
        sa.Column("max_products", sa.Integer(), nullable=True),
        sa.Column("max_clients", sa.Integer(), nullable=True),
        sa.Column("max_invoices_per_month", sa.Integer(), nullable=True),
        sa.Column("features", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("code"),
    )

    plans = sa.table(
        "subscription_plans",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("monthly_price", sa.Float),
        sa.column("annual_price", sa.Float),
        sa.column("currency", sa.String),
        sa.column("max_sub_users", sa.Integer),
        sa.column("max_products", sa.Integer),
        sa.column("max_clients", sa.Integer),
        sa.column("max_invoices_per_month", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("is_featured", sa.Boolean),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        plans,
        [
            {
                "code": "bronze_free",
                "name": "Bronze Gratuit",
                "description": "Pour découvrir Trade Care et démarrer une petite activité.",
                "monthly_price": 0,
                "annual_price": 0,
                "currency": "XOF",
                "max_sub_users": 0,
                "max_products": 100,
                "max_clients": 100,
                "max_invoices_per_month": 20,
                "is_active": True,
                "is_featured": False,
                "sort_order": 10,
            },
            {
                "code": "bronze_classic",
                "name": "Bronze Classic",
                "description": "Pour les petites entreprises qui structurent leur gestion quotidienne.",
                "monthly_price": 5000,
                "annual_price": 50000,
                "currency": "XOF",
                "max_sub_users": 2,
                "max_products": 1000,
                "max_clients": 1000,
                "max_invoices_per_month": 200,
                "is_active": True,
                "is_featured": False,
                "sort_order": 20,
            },
            {
                "code": "gold",
                "name": "Or",
                "description": "Pour les entreprises qui veulent automatiser leur croissance.",
                "monthly_price": 12500,
                "annual_price": 125000,
                "currency": "XOF",
                "max_sub_users": 8,
                "max_products": 10000,
                "max_clients": None,
                "max_invoices_per_month": None,
                "is_active": True,
                "is_featured": True,
                "sort_order": 30,
            },
            {
                "code": "diamond_pro",
                "name": "Diamant Professionnel",
                "description": "Pour les structures importantes ayant besoin d’un accompagnement prioritaire.",
                "monthly_price": 30000,
                "annual_price": 300000,
                "currency": "XOF",
                "max_sub_users": 25,
                "max_products": None,
                "max_clients": None,
                "max_invoices_per_month": None,
                "is_active": True,
                "is_featured": False,
                "sort_order": 40,
            },
        ],
    )

    feature_sets = {
        "bronze_free": [
            "sales_purchases",
            "basic_invoice",
            "basic_qr",
            "in_app_stock_alerts",
        ],
        "bronze_classic": [
            "sales_purchases",
            "professional_invoice",
            "advanced_exports",
            "full_qr",
            "financial_dashboard",
            "reports",
            "theme_colors",
            "stock_alerts",
        ],
        "gold": [
            "sales_purchases",
            "professional_invoice",
            "advanced_exports",
            "full_qr",
            "financial_dashboard",
            "annual_comparison",
            "reports",
            "custom_theme",
            "stock_alerts",
            "client_followup",
            "product_recommendation",
            "interventions",
            "depots",
        ],
        "diamond_pro": [
            "sales_purchases",
            "professional_invoice",
            "advanced_exports",
            "full_qr",
            "financial_dashboard",
            "annual_comparison",
            "reports",
            "custom_theme",
            "stock_alerts",
            "client_followup",
            "product_recommendation",
            "interventions",
            "depots",
            "multi_depot",
            "priority_support",
            "onboarding",
        ],
    }
    for code, features in feature_sets.items():
        json_value = "[" + ",".join(f'"{feature}"' for feature in features) + "]"
        op.execute(
            "UPDATE subscription_plans "
            f"SET features = '{json_value}'::json WHERE code = '{code}'"
        )

    op.add_column(
        "subscriptions",
        sa.Column("plan_code", sa.String(length=32), nullable=True),
    )
    op.create_foreign_key(
        "fk_subscriptions_plan_code",
        "subscriptions",
        "subscription_plans",
        ["plan_code"],
        ["code"],
        ondelete="RESTRICT",
    )
    # Rattacher les abonnements historiques sans casser les clients existants.
    op.execute(
        "UPDATE subscriptions SET plan_code = CASE "
        "WHEN type = 'trial' THEN 'bronze_free' "
        "ELSE 'bronze_classic' END "
        "WHERE plan_code IS NULL"
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_subscriptions_plan_code",
        "subscriptions",
        type_="foreignkey",
    )
    op.drop_column("subscriptions", "plan_code")
    op.drop_table("subscription_plans")
