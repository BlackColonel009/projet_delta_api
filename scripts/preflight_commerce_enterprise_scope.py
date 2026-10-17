"""Audit en lecture seule avant le rattachement commerce/finance."""

from __future__ import annotations

import json

from sqlalchemy import text

from app.database import engine


CHECKS = {
    "sales_without_owner_enterprise": """
        SELECT count(*) FROM commandes_ventes c
        LEFT JOIN enterprise_groups g ON g.owner_user_id = c.user_id
        LEFT JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE
        WHERE e.id IS NULL
    """,
    "purchases_without_owner_enterprise": """
        SELECT count(*) FROM commandes_achats c
        LEFT JOIN enterprise_groups g ON g.owner_user_id = c.user_id
        LEFT JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE
        WHERE e.id IS NULL
    """,
    "expenses_without_owner_enterprise": """
        SELECT count(*) FROM depenses d
        LEFT JOIN enterprise_groups g ON g.owner_user_id = d.user_id
        LEFT JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE
        WHERE e.id IS NULL
    """,
    "sale_client_owner_mismatch": """
        SELECT count(*) FROM commandes_ventes c
        JOIN clients client ON client.id = c.client_id
        WHERE c.user_id IS DISTINCT FROM client.user_id
    """,
    "purchase_supplier_owner_mismatch": """
        SELECT count(*) FROM commandes_achats c
        JOIN fournisseurs f ON f.id = c.fournisseur_id
        WHERE c.user_id IS DISTINCT FROM f.user_id
    """,
    "sale_line_product_owner_mismatch": """
        SELECT count(*) FROM lignes_commandes_ventes line
        JOIN commandes_ventes c ON c.id = line.commande_id
        JOIN produits p ON p.id = line.produit_id
        WHERE c.user_id IS DISTINCT FROM p.user_id
    """,
    "purchase_line_product_owner_mismatch": """
        SELECT count(*) FROM lignes_commandes_achats line
        JOIN commandes_achats c ON c.id = line.commande_id
        JOIN produits p ON p.id = line.produit_id
        WHERE c.user_id IS DISTINCT FROM p.user_id
    """,
    "invoice_command_owner_mismatch": """
        SELECT count(*) FROM factures f
        LEFT JOIN commandes_ventes cv ON cv.id = f.commande_id
        LEFT JOIN commandes_achats ca ON ca.id = f.commande_achat_id
        WHERE (cv.id IS NOT NULL AND f.user_id IS DISTINCT FROM cv.user_id)
           OR (ca.id IS NOT NULL AND f.user_id IS DISTINCT FROM ca.user_id)
    """,
    "invoice_party_owner_mismatch": """
        SELECT count(*) FROM factures f
        LEFT JOIN clients c ON c.id = f.client_id
        LEFT JOIN fournisseurs s ON s.id = f.fournisseur_id
        WHERE f.user_id IS NOT NULL AND (
            (c.id IS NOT NULL AND f.user_id IS DISTINCT FROM c.user_id)
         OR (s.id IS NOT NULL AND f.user_id IS DISTINCT FROM s.user_id)
        )
    """,
    "invoices_without_scope_source": """
        SELECT count(*) FROM factures f
        LEFT JOIN commandes_ventes cv ON cv.id = f.commande_id
        LEFT JOIN commandes_achats ca ON ca.id = f.commande_achat_id
        LEFT JOIN enterprise_groups g ON g.owner_user_id = f.user_id
        LEFT JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE
        LEFT JOIN clients c ON c.id = f.client_id
        LEFT JOIN fournisseurs s ON s.id = f.fournisseur_id
        WHERE cv.id IS NULL AND ca.id IS NULL AND e.id IS NULL
          AND c.enterprise_id IS NULL AND s.enterprise_id IS NULL
    """,
    "invoice_lines_without_invoice": """
        SELECT count(*) FROM lignes_facture line
        LEFT JOIN factures f ON f.id = line.facture_id WHERE f.id IS NULL
    """,
    "payments_without_invoice": """
        SELECT count(*) FROM paiements p
        LEFT JOIN factures f ON f.id = p.facture_id WHERE f.id IS NULL
    """,
    "client_products_without_scope_source": """
        SELECT count(*) FROM client_produits cp
        LEFT JOIN commandes_ventes cv ON cv.id = cp.commande_id
        LEFT JOIN clients c ON c.id = cp.client_id
        LEFT JOIN produits p ON p.id = cp.produit_id
        WHERE cv.id IS NULL AND c.enterprise_id IS NULL AND p.enterprise_id IS NULL
    """,
    "followups_without_sale": """
        SELECT count(*) FROM client_followup f
        LEFT JOIN commandes_ventes cv ON cv.id = f.commande_id
        WHERE cv.id IS NULL
    """,
}


def main() -> int:
    with engine.connect() as connection:
        counts = {
            code: int(connection.execute(text(statement)).scalar() or 0)
            for code, statement in CHECKS.items()
        }
    blockers = sum(counts.values())
    print(
        json.dumps(
            {
                "safe_to_migrate": blockers == 0,
                "blocking_issue_count": blockers,
                "checks": counts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
