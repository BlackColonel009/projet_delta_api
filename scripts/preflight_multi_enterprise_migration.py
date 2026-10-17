"""Contrôle en lecture seule avant la fondation multi-entreprises.

Le script ne crée aucune table et ne modifie aucune ligne. Il chiffre les
groupes, entreprises principales et appartenances qui seront créés par la
migration ``j1e2f3a4b5c6`` et bloque uniquement sur les comptes orphelins.
"""

from __future__ import annotations

import json

from sqlalchemy import text

from app.database import engine


def main() -> int:
    statements = {
        "main_users": "SELECT count(*) FROM users WHERE COALESCE(is_main_user, TRUE) IS TRUE",
        "sub_users": "SELECT count(*) FROM sub_users",
        "orphan_sub_users": (
            "SELECT count(*) FROM sub_users s "
            "LEFT JOIN users u ON u.id = s.parent_user_id WHERE u.id IS NULL"
        ),
        "unnamed_companies": (
            "SELECT count(*) FROM users WHERE COALESCE(is_main_user, TRUE) IS TRUE "
            "AND NULLIF(BTRIM(COALESCE(societe_ou_entreprise, '')), '') IS NULL"
        ),
    }
    with engine.connect() as connection:
        counts = {
            key: int(connection.execute(text(statement)).scalar() or 0)
            for key, statement in statements.items()
        }

    blockers = counts["orphan_sub_users"]
    result = {
        "safe_to_migrate": blockers == 0,
        "blocking_issue_count": blockers,
        "projection": {
            "groups_to_create": counts["main_users"],
            "primary_enterprises_to_create": counts["main_users"],
            "owner_memberships_to_create": counts["main_users"],
            "local_memberships_to_create": counts["sub_users"] - blockers,
        },
        "checks": counts,
        "notes": [
            "Les entreprises sans nom utiliseront le nom d'utilisateur ou l'adresse e-mail.",
            "Aucune table métier existante n'est modifiée par cette migration.",
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
