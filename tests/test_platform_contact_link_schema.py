import unittest

from pydantic import ValidationError

from app.schemas.platform_contact_link_schema import PlatformContactLinkPayload


class PlatformContactLinkPayloadTests(unittest.TestCase):
    def test_accepts_supported_links(self):
        for url in (
            "https://example.com/trade-care",
            "mailto:contact@example.com",
            "tel:+22890000000",
        ):
            payload = PlatformContactLinkPayload(label="Contact", url=url)
            self.assertEqual(payload.url, url)

    def test_rejects_insecure_and_unknown_links(self):
        with self.assertRaises(ValidationError):
            PlatformContactLinkPayload(label="Site", url="http://example.com")
        with self.assertRaises(ValidationError):
            PlatformContactLinkPayload(
                label="Réseau",
                icon_key="unknown",
                url="https://example.com",
            )


if __name__ == "__main__":
    unittest.main()
