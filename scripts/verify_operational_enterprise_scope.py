"""Verification en lecture seule du cloisonnement operations/consigne."""

import json
from sqlalchemy import text
from app.database import engine

TABLES = (
    "interventions", "intervention_produits", "historiques_interventions",
    "rapports", "notifications", "galerie_photos", "depot_services",
    "depot_tarifs", "depots", "depot_tarif_item", "factures_depot",
)


def main() -> int:
    with engine.connect() as connection:
        tables = {}
        for table in TABLES:
            row = connection.execute(text(
                f"SELECT count(*) total, count(*) FILTER "
                f"(WHERE enterprise_id IS NULL) missing FROM {table}"
            )).one()
            tables[table] = {"total": int(row.total), "missing": int(row.missing)}
        tenant_history_missing = int(connection.execute(text("""
            SELECT count(*) FROM historiques h
            LEFT JOIN users u ON u.id = h.user_id
            WHERE h.enterprise_id IS NULL
              AND COALESCE(u.is_superuser, FALSE) IS FALSE
              AND (h.user_id IS NOT NULL OR h.sub_user_id IS NOT NULL)
        """)).scalar() or 0)
    missing = sum(item["missing"] for item in tables.values())
    valid = missing == 0 and tenant_history_missing == 0
    print(json.dumps({
        "valid": valid,
        "tables": tables,
        "tenant_history_missing": tenant_history_missing,
    }, ensure_ascii=False, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
