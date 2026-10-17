"""Verification en lecture seule apres la migration commerce/finance."""

from __future__ import annotations

import json

from sqlalchemy import text

from app.database import engine


TABLES = (
    "commandes_ventes",
    "lignes_commandes_ventes",
    "commandes_achats",
    "lignes_commandes_achats",
    "factures",
    "lignes_facture",
    "paiements",
    "depenses",
    "client_produits",
    "client_followup",
)

CONSISTENCY_CHECKS = {
    "sale_client_mismatch": """
        SELECT count(*) FROM commandes_ventes sale
        JOIN clients client ON client.id = sale.client_id
        WHERE sale.enterprise_id IS DISTINCT FROM client.enterprise_id
    """,
    "purchase_supplier_mismatch": """
        SELECT count(*) FROM commandes_achats purchase
        JOIN fournisseurs supplier ON supplier.id = purchase.fournisseur_id
        WHERE purchase.enterprise_id IS DISTINCT FROM supplier.enterprise_id
    """,
    "sale_line_parent_or_product_mismatch": """
        SELECT count(*) FROM lignes_commandes_ventes line
        JOIN commandes_ventes sale ON sale.id = line.commande_id
        JOIN produits product ON product.id = line.produit_id
        WHERE line.enterprise_id IS DISTINCT FROM sale.enterprise_id
           OR line.enterprise_id IS DISTINCT FROM product.enterprise_id
    """,
    "purchase_line_parent_or_product_mismatch": """
        SELECT count(*) FROM lignes_commandes_achats line
        JOIN commandes_achats purchase ON purchase.id = line.commande_id
        JOIN produits product ON product.id = line.produit_id
        WHERE line.enterprise_id IS DISTINCT FROM purchase.enterprise_id
           OR line.enterprise_id IS DISTINCT FROM product.enterprise_id
    """,
    "invoice_command_or_party_mismatch": """
        SELECT count(*) FROM factures invoice
        LEFT JOIN commandes_ventes sale ON sale.id = invoice.commande_id
        LEFT JOIN commandes_achats purchase ON purchase.id = invoice.commande_achat_id
        LEFT JOIN clients client ON client.id = invoice.client_id
        LEFT JOIN fournisseurs supplier ON supplier.id = invoice.fournisseur_id
        WHERE (sale.id IS NOT NULL AND invoice.enterprise_id IS DISTINCT FROM sale.enterprise_id)
           OR (purchase.id IS NOT NULL AND invoice.enterprise_id IS DISTINCT FROM purchase.enterprise_id)
           OR (client.id IS NOT NULL AND invoice.enterprise_id IS DISTINCT FROM client.enterprise_id)
           OR (supplier.id IS NOT NULL AND invoice.enterprise_id IS DISTINCT FROM supplier.enterprise_id)
    """,
    "invoice_line_mismatch": """
        SELECT count(*) FROM lignes_facture line
        JOIN factures invoice ON invoice.id = line.facture_id
        WHERE line.enterprise_id IS DISTINCT FROM invoice.enterprise_id
    """,
    "payment_invoice_mismatch": """
        SELECT count(*) FROM paiements payment
        JOIN factures invoice ON invoice.id = payment.facture_id
        WHERE payment.enterprise_id IS DISTINCT FROM invoice.enterprise_id
    """,
    "client_product_sale_mismatch": """
        SELECT count(*) FROM client_produits item
        JOIN commandes_ventes sale ON sale.id = item.commande_id
        WHERE item.enterprise_id IS DISTINCT FROM sale.enterprise_id
    """,
    "followup_sale_mismatch": """
        SELECT count(*) FROM client_followup followup
        JOIN commandes_ventes sale ON sale.id = followup.commande_id
        WHERE followup.enterprise_id IS DISTINCT FROM sale.enterprise_id
    """,
}


def main() -> int:
    with engine.connect() as connection:
        tables = {}
        for table in TABLES:
            row = connection.execute(
                text(
                    f"SELECT count(*) AS total, "
                    f"count(*) FILTER (WHERE enterprise_id IS NULL) AS missing "
                    f"FROM {table}"
                )
            ).one()
            tables[table] = {"total": int(row.total), "missing": int(row.missing)}

        inconsistencies = {
            code: int(connection.execute(text(statement)).scalar() or 0)
            for code, statement in CONSISTENCY_CHECKS.items()
        }
        trigger_count = int(
            connection.execute(
                text(
                    "SELECT count(*) FROM pg_trigger "
                    "WHERE NOT tgisinternal AND tgname = ANY(:names)"
                ),
                {
                    "names": [
                        f"trg_{table}_assign_enterprise" for table in TABLES
                    ]
                },
            ).scalar()
            or 0
        )

    missing = sum(item["missing"] for item in tables.values())
    mismatch = sum(inconsistencies.values())
    ok = missing == 0 and mismatch == 0 and trigger_count == len(TABLES)
    print(
        json.dumps(
            {
                "valid": ok,
                "tables": tables,
                "inconsistencies": inconsistencies,
                "enterprise_trigger_count": trigger_count,
                "expected_trigger_count": len(TABLES),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
