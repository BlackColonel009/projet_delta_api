"""Vérification en lecture seule après migration ``business_type``."""

import json

from sqlalchemy import text

from app.database import engine


def main() -> int:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT business_type, count(*) AS total FROM enterprises "
                "GROUP BY business_type ORDER BY business_type"
            )
        ).mappings().all()
        missing = int(
            connection.execute(
                text("SELECT count(*) FROM enterprises WHERE business_type IS NULL")
            ).scalar()
            or 0
        )
        invalid = int(
            connection.execute(
                text(
                    "SELECT count(*) FROM enterprises "
                    "WHERE business_type NOT IN ('commerce', 'laundry', "
                    "'vehicle_rental', 'property_rental', 'legacy_consignment')"
                )
            ).scalar()
            or 0
        )
        wrong_legacy_mapping = int(
            connection.execute(
                text(
                    "SELECT count(*) FROM enterprises "
                    "WHERE enterprise_type = 'consigne' "
                    "AND business_type <> 'legacy_consignment'"
                )
            ).scalar()
            or 0
        )

    valid = missing == 0 and invalid == 0 and wrong_legacy_mapping == 0
    result = {
        "valid": valid,
        "business_types": {row["business_type"]: int(row["total"]) for row in rows},
        "missing_business_type": missing,
        "invalid_business_type": invalid,
        "invalid_legacy_consignment_mapping": wrong_legacy_mapping,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
