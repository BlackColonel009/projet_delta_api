from datetime import date


PRIVACY_POLICY_VERSION = "2026-11-02"
PRIVACY_POLICY_EFFECTIVE_DATE = date(2026, 11, 2)
PRIVACY_CONTACT_EMAIL = "imlogang009@gmail.com"
PRIVACY_PUBLIC_URL = (
    "https://site.trade-care.newtechnologiestg.com/confidentialite.html"
)


def public_privacy_policy_metadata() -> dict[str, str]:
    return {
        "version": PRIVACY_POLICY_VERSION,
        "effective_date": PRIVACY_POLICY_EFFECTIVE_DATE.isoformat(),
        "contact_email": PRIVACY_CONTACT_EMAIL,
        "public_url": PRIVACY_PUBLIC_URL,
    }
