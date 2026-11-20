import unittest
from datetime import datetime
from unittest.mock import patch

import app.main  # noqa: F401 - charge tous les modèles
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.model_client import Client
from app.models.model_categorie import Categorie
from app.models.model_client_produit import ClientProduit
from app.models.model_commande import CommandeAchat
from app.models.model_enterprise import Enterprise
from app.models.model_facture import Facture, LigneFacture, TypeFacture
from app.models.model_fournisseur import Fournisseur
from app.models.model_paiement import Paiement
from app.models.model_produit import Produit
from app.models.model_unite_produit import UniteProduit
from app.models.model_user import User
from app.routes.client_produit import get_produits_by_client, get_client_produit
from app.routes.commande import create_commande_achat
from app.routes.dashboard_financier import _payment_total, _sales_metrics
from app.routes.facture import add_custom_invoice_line, update_invoice_adjustments
from app.schemas.commande_schema import CommandeAchatCreate
from app.schemas.client_produit_schema import ClientProduitOut
from app.schemas.facture_schema import InvoiceCustomLineCreate, InvoiceAdjustmentUpdate
from app.services.enterprise_service import create_owner_foundation
from app.services.simple_invoice_renderer import render_simple_invoice
from app.services.generate_facture_from_commande import generate_facture_pdf
from pypdf import PdfReader


class InvoiceClientPurchaseIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.owner = User(email='test@example.com', password_hash='x', is_main_user=True, devise='XOF')
        self.db.add(self.owner)
        self.db.flush()
        group, self.enterprise = create_owner_foundation(self.db, self.owner)
        self.owner.active_enterprise_id = self.enterprise.id
        self.owner.active_enterprise_is_primary = True
        self.client = Client(nom='Client test', user_id=self.owner.id, enterprise_id=self.enterprise.id)
        self.db.add(self.client)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _invoice(self, kind=TypeFacture.vente, status='payée'):
        invoice = Facture(type=kind, statut=status, client_id=self.client.id,
                          user_id=self.owner.id, enterprise_id=self.enterprise.id,
                          total_ht=100, total_ttc=100, tva=0)
        self.db.add(invoice)
        self.db.flush()
        return invoice

    def test_custom_line_is_visible_once_and_updates_financial_totals(self):
        invoice = self._invoice()
        self.db.add(LigneFacture(facture_id=invoice.id, description='Article', quantite=1,
                                 prix_unitaire=100, total_ligne=100, enterprise_id=self.enterprise.id))
        self.db.add(Paiement(facture_id=invoice.id, montant=100,
                             user_id=self.owner.id, enterprise_id=self.enterprise.id))
        self.db.commit()
        response = add_custom_invoice_line(
            invoice.id, InvoiceCustomLineCreate(description='Livraison', quantite=2,
                                                prix_unitaire=25, unite='service'),
            db=self.db, current_user=self.owner,
        )
        self.assertEqual(response['total_ttc'], 150)
        self.assertEqual(response['statut'], 'partielle')
        rows = get_produits_by_client(self.client.id, db=self.db, current_user=self.owner)
        self.assertEqual(len(rows), 2)
        new_line = next(item for item in rows if item['nom_produit'] == 'Livraison')
        self.assertEqual(ClientProduitOut.model_validate(new_line).nom_produit, 'Livraison')
        self.assertEqual(get_client_produit(new_line['id'], db=self.db, current_user=self.owner)['quantite'], 2)
        self.assertEqual(self.db.query(ClientProduit).count(), 0)
        metrics = _sales_metrics(self.db, self.enterprise.id, datetime.utcnow().year)
        self.assertEqual(metrics['invoiced_ttc'], 150)
        self.assertEqual(_payment_total(self.db, self.enterprise.id, datetime.utcnow().year, TypeFacture.vente), 100)
        invoice.statut = 'annulée'
        self.db.commit()
        self.assertEqual(get_produits_by_client(self.client.id, db=self.db, current_user=self.owner), [])

    def test_proforma_and_other_enterprise_are_excluded(self):
        proforma = self._invoice(TypeFacture.proforma, 'en attente')
        self.db.add(LigneFacture(facture_id=proforma.id, description='Proposition', quantite=1,
                                 prix_unitaire=10, total_ligne=10, enterprise_id=self.enterprise.id))
        self.db.commit()
        self.assertEqual(get_produits_by_client(self.client.id, db=self.db, current_user=self.owner), [])

    def test_discount_vat_and_locked_payments(self):
        invoice = self._invoice(status='non payée')
        invoice.total_ht = 100000
        invoice.total_ttc = 118000
        invoice.tva = 18000  # ancienne facture issue d'une commande : montant, pas taux
        self.db.add(LigneFacture(facture_id=invoice.id, description='Article', quantite=1,
                                 prix_unitaire=100000, total_ligne=100000, enterprise_id=self.enterprise.id))
        self.db.commit()
        result = update_invoice_adjustments(invoice.id, InvoiceAdjustmentUpdate(
            remise_ht=10000, taux_tva=18, afficher_remise=False), db=self.db, current_user=self.owner)
        self.assertEqual(result['total_ht'], 90000)
        self.assertEqual(result['montant_tva'], 16200)
        self.assertEqual(result['total_ttc'], 106200)
        self.assertFalse(invoice.afficher_remise)
        add_custom_invoice_line(invoice.id, InvoiceCustomLineCreate(
            description='Service', quantite=1, prix_unitaire=10000),
            db=self.db, current_user=self.owner)
        self.assertEqual(invoice.total_ht, 100000)
        self.assertEqual(invoice.total_ttc, 118000)
        self.db.add(Paiement(facture_id=invoice.id, montant=90000,
                            user_id=self.owner.id, enterprise_id=self.enterprise.id))
        self.db.commit()
        with self.assertRaises(HTTPException):
            update_invoice_adjustments(invoice.id, InvoiceAdjustmentUpdate(
                remise_ht=21000, taux_tva=0), db=self.db, current_user=self.owner)
        result = update_invoice_adjustments(invoice.id, InvoiceAdjustmentUpdate(
            remise_ht=0, taux_tva=0), db=self.db, current_user=self.owner)
        self.assertEqual(result['total_ttc'], 110000)
        self.assertEqual(invoice.statut, 'partielle')
        invoice.statut = 'payée'
        self.db.commit()
        with self.assertRaises(HTTPException):
            update_invoice_adjustments(invoice.id, InvoiceAdjustmentUpdate(
                remise_ht=1, taux_tva=0), db=self.db, current_user=self.owner)

    def test_discount_line_visible_or_hidden_in_both_pdf_formats(self):
        import os
        invoice = self._invoice(status='non payée')
        invoice.total_ht, invoice.total_ttc = 90000, 106200
        invoice.remise_ht, invoice.taux_tva_snapshot = 10000, 18
        self.db.add(LigneFacture(facture_id=invoice.id, description='Article', quantite=1,
                                 prix_unitaire=100000, total_ligne=100000, enterprise_id=self.enterprise.id))
        self.db.commit()
        for visible in (True, False):
            invoice.afficher_remise = visible
            simple = render_simple_invoice(invoice, self.db, self.owner)
            simple_text = ''.join(page.extract_text() for page in PdfReader(simple).pages)
            pdf_path = generate_facture_pdf(invoice, self.db)
            try:
                professional_text = ''.join(page.extract_text() for page in PdfReader(pdf_path).pages)
            finally:
                os.remove(pdf_path)
            for text in (simple_text, professional_text):
                self.assertEqual('Remise HT' in text, visible)
                self.assertIn('106', text)

    def test_legacy_customer_purchase_is_scoped_to_primary_enterprise(self):
        self.db.add(ClientProduit(client_id=self.client.id, quantite=1,
                                  prix_unitaire=10, nom_produit='Ancien article'))
        self.db.commit()
        rows = get_produits_by_client(self.client.id, db=self.db, current_user=self.owner)
        self.assertEqual(len(rows), 1)
        self.assertEqual(ClientProduitOut.model_validate(rows[0]).nom_produit, 'Ancien article')
        annex = Enterprise(group_id=self.enterprise.group_id, name='Annexe', code='annexe', currency='XOF')
        self.db.add(annex)
        self.db.commit()
        self.owner.active_enterprise_id = annex.id
        self.owner.active_enterprise_is_primary = False
        with self.assertRaises(HTTPException):
            get_produits_by_client(self.client.id, db=self.db, current_user=self.owner)

    def test_supplier_purchase_rolls_back_when_invoice_creation_fails(self):
        supplier = Fournisseur(nom='Fournisseur', user_id=self.owner.id, enterprise_id=self.enterprise.id)
        category = Categorie(nom='Test', user_id=self.owner.id, enterprise_id=self.enterprise.id)
        self.db.add(category)
        self.db.flush()
        product = Produit(nom='Article', prix_achat=10, prix_vente=20, quantite=0,
                          categorie_id=category.id, user_id=self.owner.id, enterprise_id=self.enterprise.id)
        self.db.add_all([supplier, product])
        self.db.commit()
        data = CommandeAchatCreate(fournisseur_id=supplier.id, tva_appliquee=False,
                                   lignes=[{'produit_id': product.id, 'quantite': 2, 'prix_unitaire': 10}])
        with patch('app.routes.commande.enforce_invoice_quota'), \
             patch('app.routes.commande.resolve_subscription_access') as access, \
             patch('app.routes.commande.generate_facture_from_commande', side_effect=RuntimeError('test')):
            access.return_value.has_feature.return_value = True
            with self.assertRaises(HTTPException):
                create_commande_achat(data, db=self.db, current_user=self.owner)
        self.assertEqual(self.db.query(CommandeAchat).count(), 0)
        self.assertEqual(self.db.query(UniteProduit).count(), 0)
        self.assertEqual(self.db.query(Produit).filter_by(id=product.id).one().quantite, 0)

    def test_supplier_purchase_creates_invoice_and_stock_together(self):
        supplier = Fournisseur(nom='Fournisseur', user_id=self.owner.id, enterprise_id=self.enterprise.id)
        category = Categorie(nom='Test', user_id=self.owner.id, enterprise_id=self.enterprise.id)
        self.db.add_all([supplier, category])
        self.db.flush()
        product = Produit(nom='Article', prix_achat=10, prix_vente=20, quantite=0,
                         categorie_id=category.id, user_id=self.owner.id, enterprise_id=self.enterprise.id)
        self.db.add(product)
        self.db.commit()
        data = CommandeAchatCreate(fournisseur_id=supplier.id, tva_appliquee=False,
                                   lignes=[{'produit_id': product.id, 'quantite': 2, 'prix_unitaire': 10}])
        with patch('app.routes.commande.enforce_invoice_quota'), \
             patch('app.routes.commande.resolve_subscription_access') as access:
            access.return_value.has_feature.return_value = True
            result = create_commande_achat(data, db=self.db, current_user=self.owner)
        self.assertEqual(result['message'], 'Commande achat creee')
        self.assertEqual(self.db.query(CommandeAchat).count(), 1)
        self.assertEqual(self.db.query(UniteProduit).count(), 2)
        self.assertEqual(self.db.query(Facture).filter_by(type=TypeFacture.achat).count(), 1)
        self.assertEqual(self.db.query(Produit).filter_by(id=product.id).one().quantite, 2)


if __name__ == '__main__':
    unittest.main()
