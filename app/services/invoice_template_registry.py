"""Stable registry of invoice layouts exposed to the API and renderers."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class InvoiceTemplateDefinition:
    code: str
    family: str
    name_fr: str
    name_en: str
    description_fr: str
    description_en: str


SIMPLE_TEMPLATES = (
    InvoiceTemplateDefinition(
        "simple_classic",
        "simple",
        "Classique",
        "Classic",
        "Clair, compact et adapté à l'impression quotidienne.",
        "Clear, compact and suited to everyday printing.",
    ),
    InvoiceTemplateDefinition(
        "simple_compact",
        "simple",
        "Compact",
        "Compact",
        "Densité optimisée pour les factures comportant beaucoup d'articles.",
        "Optimized density for invoices containing many items.",
    ),
    InvoiceTemplateDefinition(
        "simple_receipt",
        "simple",
        "Reçu moderne",
        "Modern receipt",
        "Lecture rapide avec total et statut de paiement mis en avant.",
        "Fast reading with prominent total and payment status.",
    ),
)

PROFESSIONAL_TEMPLATES = (
    InvoiceTemplateDefinition(
        "professional_signature",
        "professional",
        "Signature",
        "Signature",
        "Identité d'entreprise élégante et blocs structurés.",
        "Elegant company identity and structured information blocks.",
    ),
    InvoiceTemplateDefinition(
        "professional_executive",
        "professional",
        "Exécutif",
        "Executive",
        "Hiérarchie forte pour les documents de direction.",
        "Strong hierarchy for executive documents.",
    ),
    InvoiceTemplateDefinition(
        "professional_modern",
        "professional",
        "Modern Flow",
        "Modern Flow",
        "Composition contemporaine, aérée et dynamique.",
        "Contemporary, spacious and dynamic composition.",
    ),
    InvoiceTemplateDefinition(
        "professional_minimal",
        "professional",
        "Minimal",
        "Minimal",
        "Sobriété premium centrée sur les données essentielles.",
        "Premium restraint focused on essential data.",
    ),
    InvoiceTemplateDefinition(
        "professional_ledger",
        "professional",
        "Grand livre",
        "Ledger",
        "Présentation rigoureuse inspirée des documents comptables.",
        "Rigorous presentation inspired by accounting documents.",
    ),
    InvoiceTemplateDefinition(
        "professional_boutique",
        "professional",
        "Boutique",
        "Boutique",
        "Style chaleureux pour le commerce et la relation client.",
        "A warm style for retail and customer relationships.",
    ),
    InvoiceTemplateDefinition(
        "professional_tech",
        "professional",
        "Tech Grid",
        "Tech Grid",
        "Grille précise pour les produits techniques et leurs caractéristiques.",
        "A precise grid for technical products and specifications.",
    ),
    InvoiceTemplateDefinition(
        "professional_elegant",
        "professional",
        "Élégance",
        "Elegance",
        "Finition raffinée pour devis et factures haut de gamme.",
        "A refined finish for premium quotes and invoices.",
    ),
)

ALL_TEMPLATES = SIMPLE_TEMPLATES + PROFESSIONAL_TEMPLATES
TEMPLATES_BY_CODE = {template.code: template for template in ALL_TEMPLATES}


def validate_template_code(code: str, family: str) -> str:
    template = TEMPLATES_BY_CODE.get(code)
    if template is None or template.family != family:
        raise ValueError(f"Unknown {family} invoice template: {code}")
    return code


def serialized_catalog() -> dict[str, list[dict]]:
    return {
        "simple": [asdict(template) for template in SIMPLE_TEMPLATES],
        "professional": [asdict(template) for template in PROFESSIONAL_TEMPLATES],
    }
