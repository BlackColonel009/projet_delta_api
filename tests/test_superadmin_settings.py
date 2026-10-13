import inspect
import unittest

from app.routes.unite_produit import purge_temp_units
from app.utils.security import require_super_user


class SuperAdminSettingsTests(unittest.TestCase):
    def test_global_temporary_unit_purge_requires_superadmin(self):
        dependency = inspect.signature(purge_temp_units).parameters[
            "current_user"
        ].default.dependency

        self.assertIs(dependency, require_super_user)

if __name__ == "__main__":
    unittest.main()
