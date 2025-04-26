# 📡 ROUTES POUR LA FACTURATION
# Fichier : app/routes/facture.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.model_facture import Facture, LigneFacture, TypeFacture
from app.models.model_produit import Produit
from app.schemas.facture_schema import FactureOut, FactureCreate
from fastapi.responses import FileResponse
import os

router = APIRouter(prefix="/factures", tags=["Facturation"])

# ➕ Créer une facture complète
@router.post("/", response_model=FactureOut)
def create_facture(data: FactureCreate, db: Session = Depends(get_db)):
    total_ht = sum(l.quantite * l.prix_unitaire for l in data.lignes)
    total_ttc = total_ht * (1 + data.tva / 100)

    facture = Facture(
        type=data.type,
        client_id=data.client_id,
        fournisseur_id=data.fournisseur_id,
        remarques=data.remarques,
        tva=data.tva,
        total_ht=total_ht,
        total_ttc=total_ttc
    )

    db.add(facture)
    db.flush()  # Pour générer facture.id

    for ligne in data.lignes:
        ligne_facture = LigneFacture(
            facture_id=facture.id,
            produit_id=ligne.produit_id,
            description=ligne.description,
            quantite=ligne.quantite,
            prix_unitaire=ligne.prix_unitaire,
            total_ligne=ligne.quantite * ligne.prix_unitaire
        )
        db.add(ligne_facture)

    db.commit()
    db.refresh(facture)
    return facture

# 🔍 Lire une facture avec ses lignes
@router.get("/{facture_id}", response_model=FactureOut)
def get_facture(facture_id: int, db: Session = Depends(get_db)):
    facture = db.query(Facture).filter(Facture.id == facture_id).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    return facture


# 🔄 Mettre à jour le statut d'une facture
@router.patch("/{facture_id}/statut", response_model=dict)
def update_facture_statut(facture_id: int, statut: str, db: Session = Depends(get_db)):
    facture = db.query(Facture).filter(Facture.id == facture_id).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    facture.statut = statut
    db.commit()
    return {"message": f"Statut de la facture #{facture_id} mis à jour en '{statut}'"}


# 📋 Lister toutes les factures
@router.get("/", response_model=List[FactureOut])
def list_factures(db: Session = Depends(get_db)):
    return db.query(Facture).all()



@router.get("/{facture_id}/open")
async def open_facture_pdf(facture_id: int):
    """
    📄 Ouvre un PDF de facture générée dans le navigateur
    """
    pdf_path = f"factures/facture_{facture_id}.pdf"

    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Facture PDF non trouvée.")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"facture_{facture_id}.pdf",
        headers={"Content-Disposition": f"inline; filename=facture_{facture_id}.pdf"}  # ➡️ inline pour ouvrir directement
    )