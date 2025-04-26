# app/main.py

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth  # Tu ajouteras d'autres routes ici
from app.config import settings
from app.routes import client
from app.routes import produit
from app.routes import categorie
from app.routes import fournisseur
from app.routes import intervention
from app.routes import historique_intervention
from app.routes import historique_general
from app.routes import commande
from app.routes import facture
from app.routes import facture_pdf
from app.routes import paiement
from app.utils.logger import log_action
from app.routes import dashboard_financier
from app.routes import depense
from app.routes import export_financier
from app.utils.security import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_current_sub_user,
    require_role, require_any_role, require_super_user
)


app = FastAPI(
    title="Projet DELTA API",
    description="API de gestion d'entreprise (petite, moyenne, grande) 📊",
    version="1.0.0"
)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tu pourras restreindre plus tard
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusion des routes
app.include_router(auth.router, prefix="/auth", tags=["Authentification"])

app.mount("/static", StaticFiles(directory="upload"), name="static")

app.include_router(client.router)

app.include_router(produit.router)

app.include_router(categorie.router)

app.include_router(fournisseur.router)

app.include_router(intervention.router)

app.include_router(historique_intervention.router)

app.include_router(historique_general.router)

app.include_router(facture.router)

app.include_router(facture_pdf.router)

app.include_router(commande.router_ventes)
app.include_router(commande.router_achats)

app.include_router(paiement.router)

app.include_router(dashboard_financier.router)

app.include_router(depense.router)

app.include_router(export_financier.router)

# Route de test
@app.get("/", tags=["Test"])
def read_root():
    return {"message": "Bienvenue sur l’API du Projet DELTA 🚀"}

@app.get("/dashboard/manager", dependencies=[Depends(require_role("manager"))])
def manager_dashboard():
    return {"message": "Bienvenue Manager 👨‍💼"}

@app.get("/shared", dependencies=[Depends(require_any_role(["viewer", "editor", "manager"]))])
def shared_dashboard():
    return {"message": "Accès pour plusieurs rôles 👥"}


