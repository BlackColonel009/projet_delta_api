"""Catalogue central des métiers disponibles dans Trade Care.

Le registre est volontairement indépendant des rôles et de la position
principale/annexe. Il devient la source unique pour la création, les capacités
et, progressivement, les sidebars spécialisées.
"""

BUSINESS_TYPE_REGISTRY = {
    "commerce": {
        "label_fr": "Commerce et gestion de stock",
        "label_en": "Commerce and inventory",
        "service_code": "gestion_principale",
        "capabilities": [
            "inventory",
            "sales",
            "purchases",
            "billing",
            "customers",
            "notifications",
            "reports",
        ],
        "is_creatable": True,
    },
    "laundry": {
        "label_fr": "Pressing et blanchisserie",
        "label_en": "Laundry and dry cleaning",
        "service_code": "laundry",
        "capabilities": [
            "laundry_orders",
            "billing",
            "customers",
            "notifications",
            "reports",
        ],
        "is_creatable": True,
    },
    "vehicle_rental": {
        "label_fr": "Location de véhicules",
        "label_en": "Vehicle rental",
        "service_code": "vehicle_rental",
        "capabilities": [
            "vehicle_fleet",
            "reservations",
            "rentals",
            "maintenance",
            "billing",
            "customers",
            "notifications",
            "reports",
        ],
        "is_creatable": True,
    },
    "property_rental": {
        "label_fr": "Location immobilière",
        "label_en": "Property rental",
        "service_code": "property_rental",
        "capabilities": [
            "properties",
            "reservations",
            "leases",
            "short_stays",
            "maintenance",
            "billing",
            "customers",
            "notifications",
            "reports",
        ],
        "is_creatable": True,
    },
    "legacy_consignment": {
        "label_fr": "Consigne historique",
        "label_en": "Legacy consignment",
        "service_code": "consigne",
        "capabilities": ["billing", "customers", "notifications", "reports"],
        "is_creatable": False,
    },
}

CREATABLE_BUSINESS_TYPES = {
    code
    for code, configuration in BUSINESS_TYPE_REGISTRY.items()
    if configuration["is_creatable"]
}


def business_type_catalog() -> list[dict]:
    return [
        {"code": code, **configuration}
        for code, configuration in BUSINESS_TYPE_REGISTRY.items()
    ]


def service_for_business_type(business_type: str) -> str:
    return BUSINESS_TYPE_REGISTRY[business_type]["service_code"]
