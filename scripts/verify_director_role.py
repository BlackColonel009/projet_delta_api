"""Controle en lecture seule du role Directeur et de ses appartenances."""

from sqlalchemy import text

from app.database import engine


def main() -> int:
    with engine.connect() as connection:
        role_count = int(
            connection.execute(
                text("SELECT count(*) FROM roles WHERE name = 'Directeur'")
            ).scalar()
            or 0
        )
        directors = int(
            connection.execute(
                text("SELECT count(*) FROM sub_users WHERE role = 'Directeur'")
            ).scalar()
            or 0
        )
        invalid_memberships = int(
            connection.execute(
                text(
                    "SELECT count(*) FROM enterprise_memberships membership "
                    "JOIN sub_users actor ON actor.id = membership.sub_user_id "
                    "WHERE actor.role = 'Directeur' AND "
                    "(membership.scope <> 'group' OR "
                    "membership.enterprise_id IS NOT NULL)"
                )
            ).scalar()
            or 0
        )
        print(f"roles_directeur={role_count}")
        print(f"subusers_directeur={directors}")
        print(f"appartenances_directeur_invalides={invalid_memberships}")
        return 0 if role_count == 1 and invalid_memberships == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
