"""Read-only post-migration checks for multi-enterprise subscriptions."""

from sqlalchemy import text

from app.database import engine


EXPECTED_LIMITS = {
    "bronze_free": 1,
    "bronze_classic": 1,
    "gold": 3,
    "diamond_pro": None,
}
EXPECTED_FEATURES = {
    "multi_enterprise",
    "group_dashboard",
    "global_stock_search",
}


def main() -> None:
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        rows = connection.execute(
            text(
                "SELECT code, max_enterprises, features "
                "FROM subscription_plans ORDER BY sort_order"
            )
        ).mappings()
        plans = {row["code"]: row for row in rows}

    assert revision == "q8f9a0b1c2d3", revision
    for code, expected_limit in EXPECTED_LIMITS.items():
        assert code in plans, f"Forfait absent: {code}"
        assert plans[code]["max_enterprises"] == expected_limit, code

    for code in ("gold", "diamond_pro"):
        features = set(plans[code]["features"] or [])
        assert EXPECTED_FEATURES <= features, code

    for code in ("bronze_free", "bronze_classic"):
        features = set(plans[code]["features"] or [])
        assert EXPECTED_FEATURES.isdisjoint(features), code

    print("revision=q8f9a0b1c2d3")
    print("plans_verified=4")
    print("multi_enterprise_features_verified=2")


if __name__ == "__main__":
    main()
