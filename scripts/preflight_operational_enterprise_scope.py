"""Audit en lecture seule avant le cloisonnement operationnel et consigne."""

import json

from sqlalchemy import text

from app.database import engine


CHECKS = {
    "interventions_without_owner_enterprise": """
        SELECT count(*) FROM interventions row
        LEFT JOIN enterprise_groups g ON g.owner_user_id = row.user_id
        LEFT JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE
        WHERE e.id IS NULL
    """,
    "intervention_client_owner_mismatch": """
        SELECT count(*) FROM interventions row JOIN clients c ON c.id = row.client_id
        WHERE row.user_id IS DISTINCT FROM c.user_id
    """,
    "intervention_product_owner_mismatch": """
        SELECT count(*) FROM intervention_produits link
        JOIN interventions i ON i.id = link.intervention_id
        JOIN produits p ON p.id = link.produit_id
        WHERE i.user_id IS DISTINCT FROM p.user_id
    """,
    "intervention_history_without_parent": """
        SELECT count(*) FROM historiques_interventions h
        LEFT JOIN interventions i ON i.id = h.intervention_id WHERE i.id IS NULL
    """,
    "reports_without_owner_enterprise": """
        SELECT count(*) FROM rapports row
        LEFT JOIN enterprise_groups g ON g.owner_user_id = row.user_id
        LEFT JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE
        WHERE e.id IS NULL
    """,
    "notifications_without_owner_enterprise": """
        SELECT count(*) FROM notifications row
        LEFT JOIN enterprise_groups g ON g.owner_user_id = row.parent_user_id
        LEFT JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE
        WHERE e.id IS NULL
    """,
    "history_without_owner_enterprise": """
        SELECT count(*) FROM historiques row
        LEFT JOIN sub_users actor ON actor.id = row.sub_user_id
        LEFT JOIN users owner ON owner.id = row.user_id
        LEFT JOIN enterprise_groups g
          ON g.owner_user_id = COALESCE(row.user_id, actor.parent_user_id)
        LEFT JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE
        WHERE COALESCE(row.user_id, actor.parent_user_id) IS NOT NULL
          AND e.id IS NULL
          AND COALESCE(owner.is_superuser, FALSE) IS FALSE
    """,
    "gallery_without_product": """
        SELECT count(*) FROM galerie_photos row
        LEFT JOIN produits p ON p.id = row.produit_id WHERE p.id IS NULL
    """,
    "services_without_owner_enterprise": """
        SELECT count(*) FROM depot_services row
        LEFT JOIN enterprise_groups g ON g.owner_user_id = row.user_id
        LEFT JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE
        WHERE e.id IS NULL
    """,
    "tariffs_without_service": """
        SELECT count(*) FROM depot_tarifs row
        LEFT JOIN depot_services s ON s.id = row.service_id WHERE s.id IS NULL
    """,
    "depots_without_consistent_source": """
        SELECT count(*) FROM depots row
        LEFT JOIN clients c ON c.id = row.client_id
        LEFT JOIN depot_services s ON s.id = row.service_id
        WHERE c.id IS NULL OR s.id IS NULL OR c.user_id IS DISTINCT FROM s.user_id
    """,
    "tariff_items_without_depot": """
        SELECT count(*) FROM depot_tarif_item row
        LEFT JOIN depots d ON d.id = row.depot_id WHERE d.id IS NULL
    """,
    "consignment_invoices_without_depot": """
        SELECT count(*) FROM factures_depot row
        LEFT JOIN depots d ON d.id = row.depot_id WHERE d.id IS NULL
    """,
}


def main() -> int:
    with engine.connect() as connection:
        counts = {
            code: int(connection.execute(text(statement)).scalar() or 0)
            for code, statement in CHECKS.items()
        }
    blockers = sum(counts.values())
    print(json.dumps({
        "safe_to_migrate": blockers == 0,
        "blocking_issue_count": blockers,
        "checks": counts,
    }, ensure_ascii=False, indent=2))
    return 0 if blockers == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
