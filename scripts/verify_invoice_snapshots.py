"""Read-only post-migration checks for immutable invoice metadata."""

from sqlalchemy import text

from app.database import engine


def main() -> None:
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        enterprise_missing = connection.execute(
            text(
                "SELECT COUNT(*) FROM enterprises WHERE "
                "simple_invoice_template IS NULL OR "
                "professional_invoice_template IS NULL"
            )
        ).scalar_one()
        invoice_missing = connection.execute(
            text(
                "SELECT COUNT(*) FROM factures WHERE "
                "technical_created_at IS NULL OR "
                "invoice_color_snapshot IS NULL OR "
                "simple_template_snapshot IS NULL OR "
                "professional_template_snapshot IS NULL"
            )
        ).scalar_one()
        deposit_missing = connection.execute(
            text(
                "SELECT COUNT(*) FROM factures_depot WHERE "
                "invoice_color_snapshot IS NULL OR "
                "simple_template_snapshot IS NULL OR "
                "professional_template_snapshot IS NULL"
            )
        ).scalar_one()

    assert revision == "r9a0b1c2d3e4", revision
    assert enterprise_missing == 0, enterprise_missing
    assert invoice_missing == 0, invoice_missing
    assert deposit_missing == 0, deposit_missing
    print("revision=r9a0b1c2d3e4")
    print("enterprise_template_gaps=0")
    print("invoice_snapshot_gaps=0")
    print("deposit_invoice_snapshot_gaps=0")


if __name__ == "__main__":
    main()
