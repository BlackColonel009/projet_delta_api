projet_delta_api/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── model_user.py
│   ├── routes/
│   │   ├── __init__.py
│   │   └── auth.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── user_schema.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── user_service.py
│   ├── utils/
│   │   ├── __init__.py
│   │   └── security.py
│   └── email/
│       ├── __init__.py
│       └── mailer.py
├── .env
├── alembic/
│   ├── versions/
│   └── (fichiers générés par alembic)
├── requirements.txt
└── README.md

import bcrypt
bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()


1. 📄 Factures
Générer des factures par vente (déjà fait ✅).

Générer des factures fournisseurs pour les achats aussi ✅.

Pouvoir modifier l’état d’une facture :

en_attente

payée

annulée

Créer un historique des paiements liés aux factures.

2. 💰 Paiements
Lorsqu'une facture est payée, enregistrer :

le montant payé,

la date du paiement,

le mode de paiement (Espèces, Virement, Chèque, Mobile Money...).

Pouvoir partiellement payer une facture (payer en plusieurs fois).

Suivre les soldes clients :

Afficher si un client te doit encore de l'argent (balance).

3. 📊 Tableau de bord Financier
Créer des dashboards pour :

Total des ventes mensuelles 📈

Total des achats mensuels 📉

Bénéfice brut = (Ventes - Achats)

TVA collectée à reverser à l’État.

Clients en retard de paiement.

Fournisseurs à payer.

➔ Graphiques pour voir l’évolution des ventes et achats mois par mois.

4. 🔄 Gestion des dépenses hors stock
Pas seulement les achats de produits :

Frais divers (loyer, internet, salaires, services extérieurs...)

Enregistrer ces dépenses dans un module Dépenses.

5. 📅 Gestion de la Trésorerie
Flux de trésorerie = Entrées (ventes, crédits) - Sorties (achats, dépenses, remboursements).

Pouvoir prévoir combien d'argent restera dans X mois.

6. 📚 Rapports financiers automatiques
Générer un bilan simple :

Total actif (stock, liquidités)

Total passif (dettes fournisseurs, crédits clients)

Générer compte de résultat : ventes - charges = résultat net.

7. ⚙️ Idées avancées
Système de rappels automatiques :

Email/SMS quand une facture approche de son échéance.

Export CSV ou PDF des rapports financiers.

Multi-devises (FCFA, €, $, selon ton besoin).

Historique des modifications financières (sécurité et audit interne).







uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload


double convertMontant({
  required double montant,
  required String from,
  required String to,
}) {
  const taux = {
    "€": 1.0,
    "\$": 1.07,
    "F CFA": 655.0,
  };

  final fromRate = taux[from] ?? 1.0;
  final toRate = taux[to] ?? 1.0;

  return montant * toRate / fromRate;
}


final totalHTUSD = convertMontant(
  montant: totalHT,
  from: selectedDevise, // la devise de base
  to: "\$",
);

final totalHTFCFA = convertMontant(
  montant: totalHT,
  from: selectedDevise,
  to: "F CFA",
);


String formatMontant(double montant, String devise) =>
    "${montant.toStringAsFixed(2)} $devise";
***********************************************************

### 📦 ClientProduit
- `GET /client-produits/client/{client_id}` – Liste des produits achetés par un client
- `GET /client-produits/{id}` – Détails d’un produit acheté
- `DELETE /client-produits/{id}` – Supprimer un lien client-produit
- 'GET /client-produits/client/{client_id}/export'
