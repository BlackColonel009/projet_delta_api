"""Préflight strictement en lecture avant l'ajout de ``business_type``."""

import json

from sqlalchemy import inspect, text

from app.database import engine


def main() -> int:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("enterprises")}
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT enterprise_type, count(*) AS total "
                "FROM enterprises GROUP BY enterprise_type ORDER BY enterprise_type"
            )
        ).mappings().all()
        missing_primary = int(
            connection.execute(
                text(
                    "SELECT count(*) FROM enterprise_groups groups "
                    "WHERE NOT EXISTS (SELECT 1 FROM enterprises enterprise "
                    "WHERE enterprise.group_id = groups.id "
                    "AND enterprise.is_primary IS TRUE)"
                )
            ).scalar()
            or 0
        )
        invalid_types = int(
            connection.execute(
                text(
                    "SELECT count(*) FROM enterprises WHERE enterprise_type "
                    "NOT IN ('principale', 'standard', 'consigne')"
                )
            ).scalar()
            or 0
        )

    safe = missing_primary == 0 and invalid_types == 0
    result = {
        "safe_to_migrate": safe,
        "business_type_already_present": "business_type" in columns,
        "enterprise_types": {
            row["enterprise_type"]: int(row["total"]) for row in rows
        },
        "groups_without_primary": missing_primary,
        "invalid_legacy_types": invalid_types,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if safe else 1


if __name__ == "__main__":
    raise SystemExit(main())
