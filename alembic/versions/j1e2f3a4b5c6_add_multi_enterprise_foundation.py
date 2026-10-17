"""add multi-enterprise foundation

Revision ID: j1e2f3a4b5c6
Revises: i0d1e2f3a4b5
Create Date: 2026-10-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j1e2f3a4b5c6"
down_revision: Union[str, None] = "i0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("owner_user_id", name="uq_enterprise_groups_owner_user_id"),
    )
    op.create_index("ix_enterprise_groups_owner_user_id", "enterprise_groups", ["owner_user_id"])

    op.create_table(
        "enterprises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("logo_url", sa.String(), nullable=True),
        sa.Column("app_theme", sa.String(length=32), nullable=False, server_default="tradecare"),
        sa.Column("theme_mode", sa.String(length=16), nullable=False, server_default="system"),
        sa.Column("invoice_color", sa.String(length=16), nullable=False, server_default="#5C6BC0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="XOF"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Africa/Lome"),
        sa.Column("map_position_x", sa.Float(), nullable=True),
        sa.Column("map_position_y", sa.Float(), nullable=True),
        sa.Column("map_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["group_id"], ["enterprise_groups.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("group_id", "code", name="uq_enterprises_group_code"),
    )
    op.create_index("ix_enterprises_group_status", "enterprises", ["group_id", "status"])
    op.execute(
        "CREATE UNIQUE INDEX uq_enterprises_one_primary_per_group "
        "ON enterprises (group_id) WHERE is_primary IS TRUE"
    )

    op.create_table(
        "enterprise_service_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enterprise_id", sa.Integer(), nullable=False),
        sa.Column("service_code", sa.String(length=48), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("configuration_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["enterprise_id"], ["enterprises.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("enterprise_id", "service_code", name="uq_enterprise_service_profiles_code"),
    )
    op.create_index("ix_enterprise_service_profiles_enterprise_id", "enterprise_service_profiles", ["enterprise_id"])

    op.create_table(
        "enterprise_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("sub_user_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("enterprise_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(length=48), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "(user_id IS NOT NULL AND sub_user_id IS NULL) OR (user_id IS NULL AND sub_user_id IS NOT NULL)",
            name="ck_enterprise_memberships_one_actor",
        ),
        sa.CheckConstraint(
            "(scope = 'group' AND enterprise_id IS NULL) OR (scope = 'enterprise' AND enterprise_id IS NOT NULL)",
            name="ck_enterprise_memberships_scope_target",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sub_user_id"], ["sub_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["enterprise_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enterprise_id"], ["enterprises.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "group_id", "scope", name="uq_enterprise_memberships_user_scope"),
        sa.UniqueConstraint("sub_user_id", "group_id", "scope", name="uq_enterprise_memberships_sub_scope"),
    )
    op.create_index("ix_enterprise_memberships_group_active", "enterprise_memberships", ["group_id", "is_active"])
    op.create_index("ix_enterprise_memberships_enterprise_active", "enterprise_memberships", ["enterprise_id", "is_active"])

    # Chaque compte actuel reçoit un groupe et une entreprise principale. Cette
    # copie n'altère aucune colonne historique et peut donc être désactivée sans
    # interrompre la version actuelle de l'application.
    op.execute(
        """
        INSERT INTO enterprise_groups (owner_user_id, name)
        SELECT u.id, COALESCE(NULLIF(BTRIM(u.societe_ou_entreprise), ''), NULLIF(BTRIM(u.username), ''), u.email)
        FROM users u
        WHERE COALESCE(u.is_main_user, TRUE) IS TRUE
        ON CONFLICT (owner_user_id) DO NOTHING
        """
    )
    op.execute(
        "INSERT INTO roles (name) SELECT 'Directeur' "
        "WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = 'Directeur')"
    )
    op.execute(
        """
        INSERT INTO enterprises (
            group_id, name, code, is_primary, status, address, phone, email,
            logo_url, app_theme, theme_mode, invoice_color, currency, map_order
        )
        SELECT g.id,
               COALESCE(NULLIF(BTRIM(u.societe_ou_entreprise), ''), NULLIF(BTRIM(u.username), ''), u.email),
               'principal-' || u.id,
               TRUE, 'active', u.addresse, u.telephone, u.email,
               u.logo_entreprise, COALESCE(u.app_theme, 'tradecare'),
               COALESCE(u.theme_mode, 'system'), COALESCE(u.facture_color, '#5C6BC0'),
               COALESCE(u.devise, 'XOF'), 0
        FROM enterprise_groups g
        JOIN users u ON u.id = g.owner_user_id
        WHERE NOT EXISTS (
            SELECT 1 FROM enterprises e WHERE e.group_id = g.id AND e.is_primary IS TRUE
        )
        """
    )
    op.execute(
        """
        INSERT INTO enterprise_service_profiles (enterprise_id, service_code, enabled, configuration_json)
        SELECT e.id, 'gestion_principale', TRUE, '{}'::json
        FROM enterprises e
        WHERE e.is_primary IS TRUE
        ON CONFLICT (enterprise_id, service_code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO enterprise_memberships (user_id, group_id, role, scope, is_active)
        SELECT g.owner_user_id, g.id, 'owner', 'group', TRUE
        FROM enterprise_groups g
        ON CONFLICT (user_id, group_id, scope) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO enterprise_memberships (
            sub_user_id, group_id, enterprise_id, role, scope, is_active
        )
        SELECT s.id, g.id, e.id, s.role, 'enterprise', TRUE
        FROM sub_users s
        JOIN enterprise_groups g ON g.owner_user_id = s.parent_user_id
        JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE
        ON CONFLICT (sub_user_id, group_id, scope) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("enterprise_memberships")
    op.drop_table("enterprise_service_profiles")
    op.drop_index("uq_enterprises_one_primary_per_group", table_name="enterprises")
    op.drop_table("enterprises")
    op.drop_table("enterprise_groups")
