"""Vérifie en lecture seule le rattachement du noyau commercial."""

from __future__ import annotations

import json

from sqlalchemy import text

from app.database import engine


TABLES = ("categories", "clients", "fournisseurs", "produits")


def main() -> int:
    counts: dict[str, int] = {}
    with engine.connect() as connection:
        for table in TABLES:
            counts[f"{table}_total"] = int(
                connection.execute(text(f"SELECT count(*) FROM {table}")).scalar()
                or 0
            )
            counts[f"{table}_without_enterprise"] = int(
                connection.execute(
                    text(f"SELECT count(*) FROM {table} WHERE enterprise_id IS NULL")
                ).scalar()
                or 0
            )
        counts["units_total"] = int(
            connection.execute(text("SELECT count(*) FROM unites_produit")).scalar()
            or 0
        )
        counts["linked_units_without_enterprise"] = int(
            connection.execute(
                text(
                    "SELECT count(*) FROM unites_produit "
                    "WHERE produit_id IS NOT NULL AND enterprise_id IS NULL"
                )
            ).scalar()
            or 0
        )
        counts["product_category_enterprise_mismatch"] = int(
            connection.execute(
                text(
                    "SELECT count(*) FROM produits p JOIN categories c "
                    "ON c.id = p.categorie_id "
                    "WHERE p.enterprise_id IS DISTINCT FROM c.enterprise_id"
                )
            ).scalar()
            or 0
        )
        counts["product_supplier_enterprise_mismatch"] = int(
            connection.execute(
                text(
                    "SELECT count(*) FROM produits p JOIN fournisseurs f "
                    "ON f.id = p.fournisseur_id "
                    "WHERE p.enterprise_id IS DISTINCT FROM f.enterprise_id"
                )
            ).scalar()
            or 0
        )
        counts["legacy_write_guards"] = int(
            connection.execute(
                text(
                    "SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal "
                    "AND tgname IN ("
                    "'trg_categories_assign_enterprise', "
                    "'trg_clients_assign_enterprise', "
                    "'trg_fournisseurs_assign_enterprise', "
                    "'trg_produits_assign_enterprise', "
                    "'trg_unites_produit_assign_enterprise')"
                )
            ).scalar()
            or 0
        )

    blocker_keys = [
        key
        for key in counts
        if key.endswith("without_enterprise") or key.endswith("mismatch")
    ]
    blockers = sum(counts[key] for key in blocker_keys)
    if counts["legacy_write_guards"] != 5:
        blockers += 5 - counts["legacy_write_guards"]
    print(
        json.dumps(
            {
                "scope_valid": blockers == 0,
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
