"""Verification en lecture seule des types d'entreprise."""

import json

from sqlalchemy import text

from app.database import engine


def main() -> int:
    with engine.connect() as connection:
        type_rows = connection.execute(
            text(
                "SELECT enterprise_type, count(*) AS total FROM enterprises "
                "GROUP BY enterprise_type ORDER BY enterprise_type"
            )
        ).all()
        invalid_primary = int(
            connection.execute(
                text(
                    "SELECT count(*) FROM enterprises "
                    "WHERE is_primary IS TRUE "
                    "AND enterprise_type <> 'principale'"
                )
            ).scalar()
            or 0
        )
        primary_missing_profiles = int(
            connection.execute(
                text(
                    "SELECT count(*) FROM enterprises enterprise "
                    "WHERE enterprise.is_primary IS TRUE AND ("
                    "SELECT count(DISTINCT profile.service_code) "
                    "FROM enterprise_service_profiles profile "
                    "WHERE profile.enterprise_id = enterprise.id "
                    "AND profile.enabled IS TRUE "
                    "AND profile.service_code IN "
                    "('gestion_principale', 'consigne')) <> 2"
                )
            ).scalar()
            or 0
        )
    result = {
        "valid": invalid_primary == 0 and primary_missing_profiles == 0,
        "enterprise_types": {row.enterprise_type: int(row.total) for row in type_rows},
        "invalid_primary_types": invalid_primary,
        "primary_enterprises_missing_required_profiles": primary_missing_profiles,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
