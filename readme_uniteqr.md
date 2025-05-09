PLAN DE MIGRATION VERS UNITÉ PAR QR CODE (Option B)
🧱 Étape 1 — Créer la table UniteProduit
✅ Modèle SQLAlchemy UniteProduit avec :

produit_id

tracabilite (QR unique)

statut (disponible, vendu, réparé, etc.)

date_creation

📁 À ajouter dans model_unite_produit.py

🛠️ Étape 2 — Adapter la logique de stock
Produit.quantite ne sera plus saisi, mais calculé dynamiquement :

python
Copier
Modifier
len(produit.unites)
Créer une route API :

http
Copier
Modifier
POST /produits/{id}/add-unites
Pour ajouter N unités avec QR uniques.

Créer une route de lecture :

http
Copier
Modifier
GET /produits/{id}/unites
🎯 Étape 3 — Adapter le scan QR
Lors d’un scan, chercher dans UniteProduit.tracabilite et non dans Produit.tracabilite.

Retourner :

les infos de l’unité

les infos du produit parent (via unite.produit)

💰 Étape 4 — Modifier les ventes & interventions
Vente = sur une UniteProduit unique

Intervention = rattachée à une UniteProduit.id, pas un Produit.id global

Créer ou modifier :

http
Copier
Modifier
POST /ventes/unite
POST /interventions/unite
🎨 Étape 5 — Ajuster le frontend (progressivement)
Page	Changement
✅ ProduitForm	pas de changement
✅ Liste produits	pas de changement
➕ Ajout de stock	devient un bouton “Ajouter X unités (QR)”
🔍 Scan QR	maintenant retourne UniteProduit
💳 Vente	scanne QR ➝ vente immédiate de cette unité
🛠️ Intervention	scanne QR ➝ rattache unité à la réparation

🧪 Étape 6 — Migration (si nécessaire)
Pour les anciens produits avec quantite > 1, proposer un outil d’admin pour créer les UniteProduit correspondants et les migrer vers la nouvelle logique.

