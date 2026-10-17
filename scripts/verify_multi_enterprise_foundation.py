"""Vérifie en lecture seule la fondation multi-entreprises après migration."""

from __future__ import annotations

import json

from sqlalchemy import text

from app.database import engine


CHECKS = {
    "groups": "SELECT count(*) FROM enterprise_groups",
    "enterprises": "SELECT count(*) FROM enterprises",
    "primary_enterprises": (
        "SELECT count(*) FROM enterprises WHERE is_primary IS TRUE"
    ),
    "service_profiles": "SELECT count(*) FROM enterprise_service_profiles",
    "memberships": "SELECT count(*) FROM enterprise_memberships",
    "owner_memberships": (
        "SELECT count(*) FROM enterprise_memberships "
        "WHERE scope = 'group' AND user_id IS NOT NULL"
    ),
    "local_memberships": (
        "SELECT count(*) FROM enterprise_memberships "
        "WHERE scope = 'enterprise' AND sub_user_id IS NOT NULL"
    ),
    "owners_without_primary": (
        "SELECT count(*) FROM enterprise_groups g WHERE NOT EXISTS "
        "(SELECT 1 FROM enterprises e "
        "WHERE e.group_id = g.id AND e.is_primary IS TRUE)"
    ),
    "subusers_without_membership": (
        "SELECT count(*) FROM sub_users s WHERE NOT EXISTS "
        "(SELECT 1 FROM enterprise_memberships m "
        "WHERE m.sub_user_id = s.id AND m.is_active IS TRUE)"
    ),
    "duplicate_primary_groups": (
        "SELECT count(*) FROM (SELECT group_id FROM enterprises "
        "WHERE is_primary IS TRUE GROUP BY group_id HAVING count(*) > 1) q"
    ),
}


def main() -> int:
    with engine.connect() as connection:
        counts = {
            key: int(connection.execute(text(statement)).scalar() or 0)
            for key, statement in CHECKS.items()
        }
    blockers = (
        counts["owners_without_primary"]
        + counts["subusers_without_membership"]
        + counts["duplicate_primary_groups"]
    )
    print(
        json.dumps(
            {
                "foundation_valid": blockers == 0,
                "blocking_issue_count": blockers,
                "counts": counts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
