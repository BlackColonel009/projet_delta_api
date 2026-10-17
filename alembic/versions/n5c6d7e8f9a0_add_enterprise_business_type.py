"""add explicit enterprise business type

Revision ID: n5c6d7e8f9a0
Revises: m4b5c6d7e8f9
Create Date: 2026-10-16

"""
from typing import Sequence, Union

from alembic import op


revision: str = "n5c6d7e8f9a0"
down_revision: Union[str, None] = "m4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE enterprises ADD COLUMN IF NOT EXISTS "
        "enterprise_type VARCHAR(32) NOT NULL DEFAULT 'standard'"
    )
    op.execute(
        "UPDATE enterprises SET enterprise_type = 'principale' "
        "WHERE is_primary IS TRUE"
    )
    op.execute(
        """
        UPDATE enterprises enterprise
        SET enterprise_type = 'consigne'
        WHERE enterprise.is_primary IS FALSE
          AND EXISTS (
              SELECT 1 FROM enterprise_service_profiles profile
              WHERE profile.enterprise_id = enterprise.id
                AND profile.service_code = 'consigne'
                AND profile.enabled IS TRUE
          )
          AND NOT EXISTS (
              SELECT 1 FROM enterprise_service_profiles profile
              WHERE profile.enterprise_id = enterprise.id
                AND profile.service_code = 'gestion_principale'
                AND profile.enabled IS TRUE
          )
        """
    )
    # L'entreprise principale conserve les deux univers deja disponibles dans
    # Trade Care. Les futures entreprises liees n'en recoivent qu'un seul.
    op.execute(
        """
        INSERT INTO enterprise_service_profiles (
            enterprise_id, service_code, enabled, configuration_json,
            created_at, updated_at
        )
        SELECT id, 'consigne', TRUE, '{}'::json, NOW(), NOW()
        FROM enterprises
        WHERE is_primary IS TRUE
        ON CONFLICT (enterprise_id, service_code)
        DO UPDATE SET enabled = TRUE, updated_at = NOW()
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            ALTER TABLE enterprises ADD CONSTRAINT ck_enterprises_type
            CHECK (enterprise_type IN ('principale', 'standard', 'consigne'));
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE enterprises DROP CONSTRAINT IF EXISTS ck_enterprises_type"
    )
    op.execute(
        "ALTER TABLE enterprises DROP COLUMN IF EXISTS enterprise_type"
    )
