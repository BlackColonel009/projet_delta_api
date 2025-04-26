from fastapi import Depends, HTTPException, status
from app.utils.security import get_current_user

def check_role(required_roles: list):
    def role_checker(current_user=Depends(get_current_user)):
        # 1️⃣ Si c'est un Main User ➔ accès total
        if getattr(current_user, "is_main_user", False):
            return current_user
        
        # 2️⃣ Sinon on vérifie le rôle du SubUser
        if not current_user.role or current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès interdit : votre rôle ne permet pas cette action."
            )
        return current_user
    return role_checker
