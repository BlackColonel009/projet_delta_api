import unittest
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main  # noqa: F401 - charge tous les modèles liés avant create_all
from app.database import Base
from app.models.model_enterprise import (
    Enterprise,
    EnterpriseGroup,
    EnterpriseMembership,
    EnterpriseServiceProfile,
)
from app.models.model_user import SubUser, User
from app.models.model_souscription import Subscription
from app.models.model_subscription_plan import SubscriptionPlan
from app.models.model_produit import Produit
from app.services.enterprise_service import (
    attach_subuser_to_enterprise,
    attach_subuser_to_primary,
    create_owner_foundation,
    resolve_active_enterprise,
    resolve_default_enterprise,
)
from app.routes.enterprise_context import (
    create_annex,
    export_group_dashboard,
    get_group_dashboard,
    search_group_products,
)
from app.schemas.enterprise_schema import EnterpriseCreate
from app.schemas.user_schema import RoleEnum


class EnterpriseFoundationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.db.add(
            SubscriptionPlan(
                code="diamond_pro",
                name="Diamant Professionnel",
                description="Test multi-entreprises",
                monthly_price=30000,
                annual_price=300000,
                currency="XOF",
                max_sub_users=25,
                max_enterprises=None,
                max_products=None,
                max_clients=None,
                max_invoices_per_month=None,
                features=[
                    "multi_enterprise",
                    "group_dashboard",
                    "global_stock_search",
                    "advanced_exports",
                ],
                is_active=True,
            )
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _owner(self, email: str, company: str) -> User:
        owner = User(
            email=email,
            password_hash="test-only",
            is_main_user=True,
            societe_ou_entreprise=company,
            devise="XOF",
        )
        self.db.add(owner)
        self.db.flush()
        self.db.add(
            Subscription(
                user_id=owner.id,
                plan_code="diamond_pro",
                type="yearly",
                status="active",
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=365),
                granted_by_admin=True,
            )
        )
        self.db.flush()
        return owner

    def test_owner_foundation_preserves_company_identity(self):
        owner = self._owner("owner@example.com", "Delta Commerce")

        group, primary = create_owner_foundation(self.db, owner)
        self.db.commit()

        self.assertEqual(group.owner_user_id, owner.id)
        self.assertEqual(primary.name, "Delta Commerce")
        self.assertTrue(primary.is_primary)
        self.assertEqual(primary.enterprise_type, "principale")
        self.assertEqual(primary.currency, "XOF")
        self.assertEqual(
            self.db.query(EnterpriseServiceProfile).filter_by(
                enterprise_id=primary.id,
                service_code="gestion_principale",
            ).count(),
            1,
        )
        self.assertEqual(
            self.db.query(EnterpriseServiceProfile).filter_by(
                enterprise_id=primary.id,
                service_code="consigne",
            ).count(),
            1,
        )
        membership = self.db.query(EnterpriseMembership).filter_by(
            user_id=owner.id
        ).one()
        self.assertEqual(membership.scope, "group")
        self.assertIsNone(membership.enterprise_id)

    def test_local_collaborator_cannot_switch_to_another_annex(self):
        owner = self._owner("owner2@example.com", "Groupe Deux")
        group, primary = create_owner_foundation(self.db, owner)
        annex = Enterprise(
            group_id=group.id,
            name="Annexe Consigne",
            code="annexe-consigne",
            is_primary=False,
            currency="XOF",
        )
        sub_user = SubUser(
            username="agent",
            password_hash="test-only",
            role="admin",
            parent_user_id=owner.id,
        )
        self.db.add_all([annex, sub_user])
        self.db.flush()
        membership = attach_subuser_to_primary(self.db, sub_user)
        self.db.commit()

        sub_user.is_main_user = False
        _, selected = resolve_active_enterprise(self.db, sub_user, primary.id)
        self.assertEqual(selected.id, primary.id)
        self.assertEqual(membership.enterprise_id, primary.id)
        _, default_enterprise = resolve_default_enterprise(self.db, sub_user)
        self.assertEqual(default_enterprise.id, primary.id)

        with self.assertRaises(HTTPException) as context:
            resolve_active_enterprise(self.db, sub_user, annex.id)
        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(
            context.exception.detail["code"],
            "ENTERPRISE_SWITCH_FORBIDDEN",
        )

    def test_group_owner_can_select_any_enterprise_in_own_group_only(self):
        owner = self._owner("owner3@example.com", "Groupe Trois")
        group, _ = create_owner_foundation(self.db, owner)
        annex = Enterprise(
            group_id=group.id,
            name="Annexe 1",
            code="annexe-1",
            currency="XOF",
        )
        other_owner = self._owner("other@example.com", "Autre Groupe")
        _, other_primary = create_owner_foundation(self.db, other_owner)
        self.db.add(annex)
        self.db.commit()

        owner.is_main_user = True
        _, selected = resolve_active_enterprise(self.db, owner, annex.id)
        self.assertEqual(selected.id, annex.id)
        _, default_enterprise = resolve_default_enterprise(self.db, owner)
        self.assertTrue(default_enterprise.is_primary)

        with self.assertRaises(HTTPException) as context:
            resolve_active_enterprise(self.db, owner, other_primary.id)
        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(context.exception.detail["code"], "ENTERPRISE_ACCESS_DENIED")

    def test_director_receives_group_scope_and_can_switch_enterprises(self):
        owner = self._owner("director-owner@example.com", "Direction")
        group, primary = create_owner_foundation(self.db, owner)
        annex = Enterprise(
            group_id=group.id,
            name="Consigne Annexe",
            code="consigne-annexe",
            enterprise_type="consigne",
            currency="XOF",
        )
        director = SubUser(
            username="direction",
            password_hash="test-only",
            role="Directeur",
            parent_user_id=owner.id,
        )
        self.db.add_all([annex, director])
        self.db.flush()
        membership = attach_subuser_to_primary(self.db, director)
        self.db.commit()
        director.is_main_user = False

        self.assertEqual(membership.scope, "group")
        self.assertIsNone(membership.enterprise_id)
        _, selected = resolve_active_enterprise(self.db, director, annex.id)
        self.assertEqual(selected.id, annex.id)

    def test_director_enum_from_registration_receives_group_scope(self):
        owner = self._owner("enum-director@example.com", "Direction Enum")
        group, _ = create_owner_foundation(self.db, owner)
        director = SubUser(
            username="direction-enum",
            password_hash="test-only",
            role=RoleEnum.directeur,
            parent_user_id=owner.id,
        )
        self.db.add(director)
        self.db.flush()

        membership = attach_subuser_to_enterprise(self.db, director)

        self.assertEqual(membership.group_id, group.id)
        self.assertEqual(membership.role, "Directeur")
        self.assertEqual(membership.scope, "group")
        self.assertIsNone(membership.enterprise_id)

    def test_local_collaborator_can_be_assigned_to_an_annex_only(self):
        owner = self._owner("annex-owner@example.com", "Groupe Annexes")
        group, primary = create_owner_foundation(self.db, owner)
        annex = Enterprise(
            group_id=group.id,
            name="Boutique Maritime",
            code="boutique-maritime",
            enterprise_type="standard",
            currency="XOF",
        )
        agent = SubUser(
            username="annex-agent",
            password_hash="test-only",
            role="admin",
            parent_user_id=owner.id,
        )
        self.db.add_all([annex, agent])
        self.db.flush()

        membership = attach_subuser_to_enterprise(self.db, agent, annex.id)
        self.db.commit()
        agent.is_main_user = False

        self.assertEqual(membership.scope, "enterprise")
        self.assertEqual(membership.enterprise_id, annex.id)
        _, default_enterprise = resolve_default_enterprise(self.db, agent)
        self.assertEqual(default_enterprise.id, annex.id)
        with self.assertRaises(HTTPException):
            resolve_active_enterprise(self.db, agent, primary.id)

    def test_collaborator_cannot_be_assigned_outside_owner_group(self):
        owner = self._owner("scope-owner@example.com", "Groupe Scope")
        create_owner_foundation(self.db, owner)
        other_owner = self._owner("foreign-owner@example.com", "Groupe Etranger")
        _, foreign_primary = create_owner_foundation(self.db, other_owner)
        agent = SubUser(
            username="scope-agent",
            password_hash="test-only",
            role="Technicien(ne)",
            parent_user_id=owner.id,
        )
        self.db.add(agent)
        self.db.flush()

        with self.assertRaises(HTTPException) as context:
            attach_subuser_to_enterprise(self.db, agent, foreign_primary.id)
        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(
            context.exception.detail["code"],
            "ENTERPRISE_ASSIGNMENT_INVALID",
        )

    def test_owner_creates_consignment_enterprise_type(self):
        owner = self._owner("owner4@example.com", "Groupe Quatre")
        create_owner_foundation(self.db, owner)
        self.db.commit()
        owner.is_main_user = True

        annex = create_annex(
            EnterpriseCreate(
                name="Agence Portuaire",
                code="Agence Portuaire",
                enterprise_type="consigne",
                timezone="Africa/Lome",
            ),
            current_user=owner,
            db=self.db,
        )

        self.assertFalse(annex.is_primary)
        self.assertEqual(annex.enterprise_type, "consigne")
        self.assertEqual(annex.code, "agence-portuaire")
        self.assertEqual(annex.map_order, 1)
        self.assertEqual(
            [profile.service_code for profile in annex.service_profiles],
            ["consigne"],
        )

    def test_enterprise_creation_stops_at_subscription_quota(self):
        owner = self._owner("quota-owner@example.com", "Groupe Limite")
        create_owner_foundation(self.db, owner)
        plan = self.db.query(SubscriptionPlan).filter_by(
            code="diamond_pro"
        ).one()
        plan.max_enterprises = 1
        self.db.commit()
        owner.is_main_user = True

        with self.assertRaises(HTTPException) as context:
            create_annex(
                EnterpriseCreate(
                    name="Annexe interdite",
                    enterprise_type="standard",
                ),
                current_user=owner,
                db=self.db,
            )

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(context.exception.detail["code"], "QUOTA_REACHED")
        self.assertEqual(
            context.exception.detail["resource"],
            "max_enterprises",
        )

    def test_group_dashboard_requires_subscription_feature(self):
        owner = self._owner("feature-owner@example.com", "Groupe Fonction")
        create_owner_foundation(self.db, owner)
        plan = self.db.query(SubscriptionPlan).filter_by(
            code="diamond_pro"
        ).one()
        plan.features = ["multi_enterprise"]
        self.db.commit()
        owner.is_main_user = True

        with self.assertRaises(HTTPException) as context:
            get_group_dashboard(current_user=owner, db=self.db)

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(
            context.exception.detail["code"],
            "FEATURE_NOT_INCLUDED",
        )

    def test_group_dashboard_and_search_are_reserved_to_group_scope(self):
        owner = self._owner("dashboard-owner@example.com", "Groupe Pilotage")
        _, primary = create_owner_foundation(self.db, owner)
        product = Produit(
            nom="Imprimante Laser",
            categorie_id=1,
            prix_achat=100,
            prix_vente=150,
            quantite=4,
            user_id=owner.id,
            enterprise_id=primary.id,
        )
        # SQLite n'applique pas ici la cle etrangere vers la categorie ; cela
        # suffit pour verifier la portee et l'agregation du nouveau endpoint.
        self.db.add(product)
        self.db.commit()
        owner.is_main_user = True

        dashboard = get_group_dashboard(current_user=owner, db=self.db)
        self.assertEqual(dashboard["enterprise_count"], 1)
        self.assertEqual(dashboard["totals"]["stock_quantity"], 4)
        results = search_group_products(
            q="Imprimante",
            current_user=owner,
            db=self.db,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["enterprise_name"], primary.name)

        local = SubUser(
            username="dashboard-local",
            password_hash="test-only",
            role="admin",
            parent_user_id=owner.id,
        )
        self.db.add(local)
        self.db.flush()
        attach_subuser_to_primary(self.db, local)
        self.db.commit()
        local.is_main_user = False
        with self.assertRaises(HTTPException) as context:
            get_group_dashboard(current_user=local, db=self.db)
        self.assertEqual(context.exception.status_code, 403)

    def test_group_dashboard_pdf_is_generated(self):
        owner = self._owner("pdf-owner@example.com", "Groupe PDF")
        create_owner_foundation(self.db, owner)
        self.db.commit()
        owner.is_main_user = True

        response = export_group_dashboard(current_user=owner, db=self.db)

        self.assertEqual(response.media_type, "application/pdf")
        self.assertIn(
            "tableau-de-bord-general.pdf",
            response.headers["content-disposition"],
        )


if __name__ == "__main__":
    unittest.main()
