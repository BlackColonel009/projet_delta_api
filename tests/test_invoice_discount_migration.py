import importlib.util
import unittest
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


class InvoiceDiscountMigrationTests(unittest.TestCase):
    def test_upgrade_preserves_legacy_invoice_values(self):
        path = Path(__file__).resolve().parents[1] / 'alembic/versions/n1k2l3m4n5o6_invoice_discount.py'
        spec = importlib.util.spec_from_file_location('invoice_discount_migration', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        engine = create_engine('sqlite:///:memory:')
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE factures (id INTEGER PRIMARY KEY, total_ht FLOAT, total_ttc FLOAT, tva FLOAT)'))
            connection.execute(text('INSERT INTO factures VALUES (1, 100000, 118000, 18000)'))
            module.op = Operations(MigrationContext.configure(connection))
            module.upgrade()
            result = connection.execute(text('SELECT total_ht, total_ttc, tva, remise_ht, taux_tva_snapshot, afficher_remise FROM factures')).one()
            self.assertEqual(tuple(result), (100000, 118000, 18000, 0, None, 1))
        engine.dispose()


if __name__ == '__main__':
    unittest.main()
