"""Audit en lecture seule avant le rattachement du noyau métier aux entreprises."""

from __future__ import annotations

import json

from sqlalchemy import text

from app.database import engine


CHECKS = {
    "categories_without_primary_enterprise": """
        SELECT count(*) FROM categories c
        LEFT JOIN enterprise_groups g ON g.owner_user_id = c.user_id
        LEFT JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE
        WHERE e.id IS NULL
    """,
    "clients_without_primary_enterprise": """
        SELECT count(*) FROM clients c
        LEFT JOIN enterprise_groups g ON g.owner_user_id = c.user_id
        LEFT JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE
        WHERE e.id IS NULL
    """,
    "suppliers_without_primary_enterprise": """
        SELECT count(*) FROM fournisseurs f
        LEFT JOIN enterprise_groups g ON g.owner_user_id = f.user_id
        LEFT JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE
        WHERE e.id IS NULL
    """,
    "products_without_primary_enterprise": """
        SELECT count(*) FROM produits p
        LEFT JOIN enterprise_groups g ON g.owner_user_id = p.user_id
        LEFT JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE
        WHERE e.id IS NULL
    """,
    "product_category_owner_mismatch": """
        SELECT count(*) FROM produits p
        JOIN categories c ON c.id = p.categorie_id
        WHERE p.user_id IS DISTINCT FROM c.user_id
    """,
    "product_supplier_owner_mismatch": """
        SELECT count(*) FROM produits p
        JOIN fournisseurs f ON f.id = p.fournisseur_id
        WHERE p.user_id IS DISTINCT FROM f.user_id
    """,
    "duplicate_category_names_after_scope": """
        SELECT count(*) FROM (
            SELECT g.id, lower(trim(c.nom))
            FROM categories c
            JOIN enterprise_groups g ON g.owner_user_id = c.user_id
            GROUP BY g.id, lower(trim(c.nom)) HAVING count(*) > 1
        ) duplicate_names
    """,
    "units_with_missing_product": """
        SELECT count(*) FROM unites_produit u
        LEFT JOIN produits p ON p.id = u.produit_id
        WHERE u.produit_id IS NOT NULL AND p.id IS NULL
    """,
    "temporary_units_without_product": """
        SELECT count(*) FROM unites_produit WHERE produit_id IS NULL
    """,
}

BLOCKING = {
    "categories_without_primary_enterprise",
    "clients_without_primary_enterprise",
    "suppliers_without_primary_enterprise",
    "products_without_primary_enterprise",
    "product_category_owner_mismatch",
    "product_supplier_owner_mismatch",
    "duplicate_category_names_after_scope",
    "units_with_missing_product",
}


def main() -> int:
    with engine.connect() as connection:
        counts = {
            code: int(connection.execute(text(statement)).scalar() or 0)
            for code, statement in CHECKS.items()
        }
    blockers = sum(counts[code] for code in BLOCKING)
    print(
        json.dumps(
            {
                "safe_to_migrate": blockers == 0,
                "blocking_issue_count": blockers,
                "checks": counts,
                "notes": [
                    "Les unités temporaires sans produit restent nulles jusqu'à leur rattachement.",
                    "Les colonnes user_id historiques sont conservées.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
