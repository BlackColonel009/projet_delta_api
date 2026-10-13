import unittest
from types import SimpleNamespace

from app.routes.dashboard_financier import merge_available_years


class DashboardYearsTests(unittest.TestCase):
    def test_years_are_merged_deduplicated_and_sorted_in_python(self):
        sales = [SimpleNamespace(year=2026), SimpleNamespace(year=2024)]
        purchases = [(2025,), (2026,)]
        expenses = [SimpleNamespace(year=None), (2023,)]

        result = merge_available_years(sales, purchases, expenses)

        self.assertEqual(result, [2023, 2024, 2025, 2026])

    def test_empty_sources_return_an_empty_list(self):
        self.assertEqual(merge_available_years([], [], []), [])


if __name__ == "__main__":
    unittest.main()
