from fastapi import Depends, HTTPException, status
from app.utils.security import get_current_user

def check_role(required_roles: list):
    def role_checker(current_user=Depends(get_current_user)):
        # 1️⃣ Si c’est un user avec un compte principal OU un compte normal
        if current_user.is_main_user or not hasattr(current_user, 'role'):
            return current_user

        # 2️⃣ Si c’est un subuser ➔ on vérifie son rôle
        if not current_user.role or current_user.role not in required_roles:
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
    return check_role(["technicien"])