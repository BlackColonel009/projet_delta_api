import unittest

from pydantic import ValidationError

from app.schemas.app_download_schema import AppDownloadUpdate


class AppDownloadUpdateTests(unittest.TestCase):
    def test_enabled_release_requires_https_url(self):
        with self.assertRaises(ValidationError):
            AppDownloadUpdate(enabled=True, download_url="http://example.com/app.apk")

        with self.assertRaises(ValidationError):
            AppDownloadUpdate(enabled=True)

    def test_valid_release_normalizes_checksum(self):
        payload = AppDownloadUpdate(
            enabled=True,
            download_url="https://mega.nz/file/example",
            sha256="A" * 64,
        )
        self.assertEqual(payload.sha256, "a" * 64)

    def test_disabled_release_can_clear_url(self):
        payload = AppDownloadUpdate(enabled=False, download_url="  ")
        self.assertIsNone(payload.download_url)


if __name__ == "__main__":
    unittest.main()
