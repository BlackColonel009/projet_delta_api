"""Audit read-only avant les migrations de stabilisation de la consigne.

Ce script ne modifie aucune donnée. Il retourne un code non nul lorsqu'une
incohérence susceptible de bloquer la migration ou de mélanger deux entreprises
est détectée.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from sqlalchemy import text

from app.database import engine


@dataclass(frozen=True)
class CheckResult:
    code: str
    label: str
    count: int
    sample_ids: list[int]
    blocking: bool = True


CHECKS = (
    (
        "duplicate_service_names",
        "Noms de service dupliqués dans une même entreprise",
        """
        SELECT min(id) AS sample_id, count(*) AS issue_count
        FROM (
            SELECT user_id, lower(trim(nom)) AS normalized_name,
                   min(id) AS id, count(*) AS duplicates
            FROM depot_services
            GROUP BY user_id, lower(trim(nom))
            HAVING count(*) > 1
        ) AS duplicates
        """,
    ),
    (
        "deposit_client_owner_mismatch",
        "Dépôts liés à un client d'une autre entreprise",
        """
        SELECT min(d.id) AS sample_id, count(*) AS issue_count
        FROM depots d
        JOIN clients c ON c.id = d.client_id
        WHERE c.user_id IS DISTINCT FROM d.user_id
        """,
    ),
    (
        "deposit_service_owner_mismatch",
        "Dépôts liés à un service d'une autre entreprise",
        """
        SELECT min(d.id) AS sample_id, count(*) AS issue_count
        FROM depots d
        JOIN depot_services s ON s.id = d.service_id
        WHERE s.user_id IS DISTINCT FROM d.user_id
        """,
    ),
    (
        "rate_item_owner_mismatch",
        "Lignes de dépôt utilisant le tarif d'une autre entreprise",
        """
        SELECT min(i.id) AS sample_id, count(*) AS issue_count
        FROM depot_tarif_item i
        JOIN depots d ON d.id = i.depot_id
        JOIN depot_tarifs t ON t.id = i.tarif_id
        WHERE t.user_id IS DISTINCT FROM d.user_id
        """,
    ),
    (
        "invoice_owner_mismatch",
        "Factures de consigne portant un propriétaire différent du dépôt",
        """
        SELECT min(f.id) AS sample_id, count(*) AS issue_count
        FROM factures_depot f
        JOIN depots d ON d.id = f.depot_id
        WHERE f.user_id IS DISTINCT FROM d.user_id
        """,
    ),
    (
        "deposit_without_invoice",
        "Dépôts sans facture de consigne associée",
        """
        SELECT min(d.id) AS sample_id, count(*) AS issue_count
        FROM depots d
        LEFT JOIN factures_depot f ON f.depot_id = d.id
        WHERE f.id IS NULL
        """,
    ),
    (
        "invoice_client_mismatch",
        "Factures rattachées à un client différent du dépôt",
        """
        SELECT min(f.id) AS sample_id, count(*) AS issue_count
        FROM factures_depot f
        JOIN depots d ON d.id = f.depot_id
        WHERE f.client_id IS DISTINCT FROM d.client_id
        """,
    ),
)


def run_checks() -> list[CheckResult]:
    results: list[CheckResult] = []
    with engine.connect() as connection:
        for code, label, statement in CHECKS:
            row = connection.execute(text(statement)).mappings().one()
            count = int(row["issue_count"] or 0)
            sample = row["sample_id"]
            results.append(
                CheckResult(
                    code=code,
                    label=label,
                    count=count,
                    sample_ids=[int(sample)] if sample is not None else [],
                )
            )
    return results


def main() -> int:
    results = run_checks()
    blockers = [result for result in results if result.blocking and result.count]
    print(
        json.dumps(
            {
                "safe_to_migrate": not blockers,
                "blocking_issue_count": sum(item.count for item in blockers),
                "checks": [asdict(item) for item in results],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
