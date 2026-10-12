import unittest
from types import SimpleNamespace

from app.routes.auth import update_company_theme
from app.schemas.user_schema import CompanyThemeUpdate


class _FakeDb:
    def __init__(self):
        self.commits = 0
        self.refreshed = None

    def commit(self):
        self.commits += 1

    def refresh(self, value):
        self.refreshed = value


class CompanyThemeTests(unittest.TestCase):
    def test_main_user_theme_is_saved(self):
        user = SimpleNamespace(
            app_theme="tradecare",
            theme_mode="system",
            is_main_user=True,
        )
        db = _FakeDb()

        result = update_company_theme(
            CompanyThemeUpdate(app_theme="emerald", theme_mode="dark"),
            db=db,
            current_user=user,
        )

        self.assertEqual(result["app_theme"], "emerald")
        self.assertEqual(result["theme_mode"], "dark")
        self.assertEqual(db.commits, 1)
        self.assertIs(db.refreshed, user)

    def test_unknown_theme_is_rejected_by_schema(self):
        with self.assertRaises(ValueError):
            CompanyThemeUpdate(app_theme="invisible", theme_mode="system")


if __name__ == "__main__":
    unittest.main()
