# init_permissions.py

from app.database import SessionLocal
from app.models.model_role import Role, Permission

# Structure initiale des rôles et permissions
role_permissions_map = {
    "Technicien(ne)": ["view_tasks", "update_tasks"],
    "Secretaire": ["view_schedule", "manage_documents"],
    "Caissier(e)": ["create_invoice", "view_payments"],
    "comptable": ["view_financials", "export_reports"],
    "Comptable": ["view_clients", "manage_deals"],
    "Gestionnaire de stock": ["view_inventory", "update_inventory"],
    "admin" : ["view_all", "update_all"]
}

db = SessionLocal()

# Création des permissions
permission_objs = {}
for perm in set(perm for perms in role_permissions_map.values() for perm in perms):
    p = db.query(Permission).filter(Permission.name == perm).first()
    if not p:
        p = Permission(name=perm)
        db.add(p)
        db.flush()
    permission_objs[perm] = p

# Création des rôles + liens
for role_name, perms in role_permissions_map.items():
    r = db.query(Role).filter(Role.name == role_name).first()
    if not r:
        r = Role(name=role_name)
        r.permissions = [permission_objs[p] for p in perms]
        db.add(r)

db.commit()
print("✅ Rôles et permissions initialisés avec succès.")
