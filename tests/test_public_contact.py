import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import public_contact


class PublicContactTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(public_contact.router)
        self.client = TestClient(app)
        public_contact.rate_limit = public_contact.ContactRateLimit()
        self.payload = dict(name="Visiteur test", email="visitor@example.com",
            company="Entreprise test", business="Commerce", plan="Or",
            billing_cycle="annual", message="Une demande de démonstration.",
            consent=True, website="")
        self.mail = patch.object(public_contact, "send_email_message", new_callable=AsyncMock)
        self.send = self.mail.start()
        self.send.return_value = True
        self.addCleanup(self.mail.stop)
        self.enabled = patch.object(public_contact.settings, "MAIL_ENABLED", True)
        self.enabled.start()
        self.addCleanup(self.enabled.stop)

    def test_sends_to_fixed_recipient_with_reply_to_and_escaped_content(self):
        self.payload["message"] = "Bonjour <script>alert(1)</script>"
        response = self.client.post("/public/contact", json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "sent")
        args = self.send.call_args.kwargs
        self.assertEqual(args["to_email"], "imlogang009@gmail.com")
        self.assertEqual(args["reply_to"], "visitor@example.com")
        self.assertIn("&lt;script&gt;", args["body"])
        self.assertNotIn("<script>", args["body"])

    def test_validation_rejects_recipient_override_and_missing_consent(self):
        for extra in ({"to_email": "other@example.com"}, {"consent": False},
                      {"email": "invalid"}, {"name": "Name\r\nInjected"}):
            response = self.client.post("/public/contact", json={**self.payload, **extra})
            self.assertEqual(response.status_code, 422)
        self.send.assert_not_called()

    def test_honeypot_and_rate_limit(self):
        response = self.client.post("/public/contact", json={**self.payload, "website": "spam"})
        self.assertEqual(response.status_code, 400)
        self.send.assert_not_called()
        for _ in range(2):
            self.assertEqual(self.client.post("/public/contact", json=self.payload).status_code, 200)
        response = self.client.post("/public/contact", json=self.payload)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "600")

    def test_smtp_failure_never_reports_success(self):
        self.send.return_value = False
        self.assertEqual(self.client.post("/public/contact", json=self.payload).status_code, 503)
        self.send.side_effect = RuntimeError("Private connection details")
        response = self.client.post("/public/contact", json=self.payload)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("Private connection", response.text)

    def test_disabled_mail_is_unavailable(self):
        with patch.object(public_contact.settings, "MAIL_ENABLED", False):
            self.assertEqual(self.client.get("/public/contact").json(), {"available": False})
            self.assertEqual(self.client.post("/public/contact", json=self.payload).status_code, 503)
        self.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
