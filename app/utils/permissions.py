from fastapi import Depends, HTTPException, status
from app.schemas.user_schema import RoleEnum
from app.utils.subscription_guard import require_active_subscription
from app.utils.enterprise_context import (
    ActiveEnterpriseContext,
    get_active_enterprise_context,
)

# def check_role(required_roles: list):
#     def role_checker(current_user=Depends(get_current_user)):
#         # 1️⃣ Si c’est un user avec un compte principal OU un compte normal
#         if current_user.is_main_user or not hasattr(current_user, 'role'):
#             return current_user

#         # 2️⃣ Si c’est un subuser ➔ on vérifie son rôle
#         if not current_user.role or current_user.role not in required_roles:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail="Accès interdit : votre rôle ne permet pas cette action."
#             )
#         return current_user
#     return role_checker

# def check_role(required_roles: list):
#     def role_checker(current_user=Depends(get_active_user)):
#         # Main user => accès total
#         if current_user.is_main_user:
#             return current_user

#         # Sub-user : on vérifie le rôle
#         if not hasattr(current_user, "role") or current_user.role not in required_roles:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail="Accès interdit : votre rôle ne permet pas cette action."
#             )
#         return current_user
#     return role_checker

def check_role(required_roles: list):
    def role_checker(
        enterprise_context: ActiveEnterpriseContext = Depends(
            get_active_enterprise_context
        ),
        _ = Depends(require_active_subscription),  # 👈 abonnement vérifié ici
    ):
        current_user = enterprise_context.actor
        # Attributs transitoires non persistés : les routes migrées peuvent
        # utiliser le contexte sans modifier la structure historique User/SubUser.
        current_user.active_enterprise_id = enterprise_context.enterprise_id
        current_user.active_enterprise_is_primary = (
            enterprise_context.enterprise.is_primary
        )
        current_user.active_enterprise_business_type = (
            enterprise_context.enterprise.business_type
        )
        current_user.enterprise_group_id = enterprise_context.group_id
        # 🟢 Superuser → accès total (ignore abonnement + rôle)
        if getattr(current_user, "is_superuser", False):
            return current_user

        # 🟢 Main user → accès total (mais abonnement requis)
        if current_user.is_main_user:
            return current_user

        # Le Directeur agit sur toutes les entreprises du groupe, sans obtenir
        # pour autant les opérations de propriété protégées par require_main_user.
        if str(getattr(current_user, "role", "")).strip().lower() == "directeur":
            return current_user

        # 🔴 Sub-user → vérification du rôle
        if not hasattr(current_user, "role") or current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès interdit : votre rôle ne permet pas cette action."
            )

        return current_user

    return role_checker


# 🎯 Raccourcis prêts à utiliser

def admin_required():
    return check_role(["admin"])

def comptable_required():
    return check_role(["comptable"])

def commercial_required():
    return check_role(["commercial"])

def stock_manager_required():
    return check_role(["gestionnaire_stock"])

def caissier_required():
    return check_role(["caissier"])

def secretaire_required():
    return check_role(["secretaire"])

def technicien_required():
    return check_role([RoleEnum.admin, RoleEnum.technicien])

def All_required():
    return check_role([RoleEnum.admin, RoleEnum.comptable, RoleEnum.commercial, RoleEnum.gestionnaire_stock, RoleEnum.caissier, RoleEnum.secretaire, RoleEnum.technicien])
