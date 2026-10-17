import re
import unicodedata

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, selectinload

from app.models.model_enterprise import (
    Enterprise,
    EnterpriseGroup,
    EnterpriseMembership,
    EnterpriseServiceProfile,
)
from app.models.model_user import SubUser, User


DEFAULT_SERVICE = "gestion_principale"
SUPPORTED_SERVICES = {DEFAULT_SERVICE, "consigne"}


def actor_owner_id(actor) -> int:
    return actor.id if getattr(actor, "is_main_user", False) else actor.parent_user_id


def actor_enterprise_id(actor) -> int:
    enterprise_id = getattr(actor, "active_enterprise_id", None)
    if not enterprise_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ACTIVE_ENTERPRISE_REQUIRED",
                "message": "Le contexte de l'entreprise active est requis.",
            },
        )
    return int(enterprise_id)


def enterprise_scope_filter(model, actor):
    """Double lecture sûre pendant la migration des anciennes données.

    Les lignes historiques sans enterprise_id ne sont visibles que depuis
    l'entreprise principale et restent filtrées par leur ancien propriétaire.
    """
    enterprise_id = actor_enterprise_id(actor)
    if getattr(actor, "active_enterprise_is_primary", False):
        return or_(
            model.enterprise_id == enterprise_id,
            and_(
                model.enterprise_id.is_(None),
                model.user_id == actor_owner_id(actor),
            ),
        )
    return model.enterprise_id == enterprise_id


def _slug(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return value[:70] or "entreprise"


def unique_enterprise_code(db: Session, group_id: int, requested: str) -> str:
    root = _slug(requested)
    candidate = root
    suffix = 2
    while db.query(Enterprise.id).filter(
        Enterprise.group_id == group_id,
        Enterprise.code == candidate,
    ).first():
        candidate = f"{root[:65]}-{suffix}"
        suffix += 1
    return candidate


def create_owner_foundation(db: Session, user: User) -> tuple[EnterpriseGroup, Enterprise]:
    """Crée le groupe d'un nouveau propriétaire dans la transaction courante."""
    existing = db.query(EnterpriseGroup).filter(
        EnterpriseGroup.owner_user_id == user.id
    ).first()
    if existing:
        primary = db.query(Enterprise).filter(
            Enterprise.group_id == existing.id,
            Enterprise.is_primary.is_(True),
        ).first()
        return existing, primary

    company_name = (user.societe_ou_entreprise or user.username or user.email).strip()
    group = EnterpriseGroup(owner_user_id=user.id, name=company_name)
    db.add(group)
    db.flush()

    enterprise = Enterprise(
        group_id=group.id,
        name=company_name,
        code=unique_enterprise_code(db, group.id, company_name),
        is_primary=True,
        enterprise_type="principale",
        address=user.addresse,
        phone=user.telephone,
        email=user.email,
        logo_url=user.logo_entreprise,
        app_theme=user.app_theme or "tradecare",
        theme_mode=user.theme_mode or "system",
        invoice_color=user.facture_color or "#5C6BC0",
        currency=user.devise or "XOF",
        map_order=0,
    )
    db.add(enterprise)
    db.flush()
    db.add_all(
        [
            EnterpriseServiceProfile(
                enterprise_id=enterprise.id,
                service_code=service_code,
                enabled=True,
                configuration_json={},
            )
            for service_code in (DEFAULT_SERVICE, "consigne")
        ]
    )
    db.add(
        EnterpriseMembership(
            user_id=user.id,
            group_id=group.id,
            role="owner",
            scope="group",
            is_active=True,
        )
    )
    db.flush()
    return group, enterprise


def attach_subuser_to_enterprise(
    db: Session,
    sub_user: SubUser,
    enterprise_id: int | None = None,
) -> EnterpriseMembership:
    """Rattache un collaborateur a sa portee autorisee.

    Un Directeur obtient toujours une portee groupe. Tous les autres roles sont
    verrouilles sur une entreprise du groupe du proprietaire. L'absence de cible
    conserve le comportement historique en choisissant l'entreprise principale.
    """
    group = db.query(EnterpriseGroup).filter(
        EnterpriseGroup.owner_user_id == sub_user.parent_user_id
    ).first()
    if not group:
        owner = db.query(User).filter(User.id == sub_user.parent_user_id).first()
        if not owner:
            raise HTTPException(status_code=404, detail="Entreprise parente introuvable")
        group, _ = create_owner_foundation(db, owner)

    membership = db.query(EnterpriseMembership).filter(
        EnterpriseMembership.sub_user_id == sub_user.id,
        EnterpriseMembership.group_id == group.id,
    ).first()
    # Pydantic peut fournir un RoleEnum juste après la création, alors qu'une
    # lecture depuis SQLAlchemy renvoie une chaîne. Normaliser les deux évite
    # d'enfermer par erreur un nouveau Directeur dans une seule annexe.
    normalized_role = str(getattr(sub_user.role, "value", sub_user.role)).strip()
    is_director = normalized_role.lower() == "directeur"
    target_enterprise = None
    if not is_director:
        enterprise_query = db.query(Enterprise).filter(
            Enterprise.group_id == group.id,
            Enterprise.status == "active",
        )
        if enterprise_id is None:
            # Une simple modification de profil ne doit pas renvoyer sans raison
            # un collaborateur d'une annexe vers l'entreprise principale.
            if membership and membership.scope == "enterprise":
                enterprise_query = enterprise_query.filter(
                    Enterprise.id == membership.enterprise_id
                )
            else:
                enterprise_query = enterprise_query.filter(
                    Enterprise.is_primary.is_(True)
                )
        else:
            enterprise_query = enterprise_query.filter(Enterprise.id == enterprise_id)
        target_enterprise = enterprise_query.first()
        if not target_enterprise:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "ENTERPRISE_ASSIGNMENT_INVALID",
                    "message": "L'entreprise d'affectation est introuvable ou n'appartient pas a ce groupe.",
                },
            )

    if membership:
        membership.role = normalized_role
        membership.scope = "group" if is_director else "enterprise"
        membership.enterprise_id = None if is_director else target_enterprise.id
        membership.is_active = True
        db.flush()
        return membership
    membership = EnterpriseMembership(
        sub_user_id=sub_user.id,
        group_id=group.id,
        enterprise_id=None if is_director else target_enterprise.id,
        role=normalized_role,
        scope="group" if is_director else "enterprise",
        is_active=True,
    )
    db.add(membership)
    db.flush()
    return membership


def attach_subuser_to_primary(db: Session, sub_user: SubUser) -> EnterpriseMembership:
    """Compatibilite avec les appels historiques et les migrations existantes."""
    return attach_subuser_to_enterprise(db, sub_user)


def resolve_membership(db: Session, actor) -> EnterpriseMembership:
    if getattr(actor, "is_main_user", False):
        membership = db.query(EnterpriseMembership).filter(
            EnterpriseMembership.user_id == actor.id,
            EnterpriseMembership.is_active.is_(True),
        ).first()
    else:
        membership = db.query(EnterpriseMembership).filter(
            EnterpriseMembership.sub_user_id == actor.id,
            EnterpriseMembership.is_active.is_(True),
        ).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ENTERPRISE_CONTEXT_MISSING",
                "message": "Le compte n'est pas encore rattaché à une entreprise.",
            },
        )
    return membership


def accessible_enterprises(db: Session, membership: EnterpriseMembership) -> list[Enterprise]:
    query = db.query(Enterprise).options(
        selectinload(Enterprise.service_profiles)
    ).filter(
        Enterprise.group_id == membership.group_id,
        Enterprise.status == "active",
    )
    if membership.scope == "enterprise":
        query = query.filter(Enterprise.id == membership.enterprise_id)
    return query.order_by(Enterprise.is_primary.desc(), Enterprise.map_order, Enterprise.id).all()


def resolve_active_enterprise(
    db: Session,
    actor,
    requested_enterprise_id: int,
) -> tuple[EnterpriseMembership, Enterprise]:
    """Valide le contexte envoyé par le client, sans jamais lui faire confiance."""
    membership = resolve_membership(db, actor)
    enterprise = db.query(Enterprise).filter(
        Enterprise.id == requested_enterprise_id,
        Enterprise.group_id == membership.group_id,
        Enterprise.status == "active",
    ).first()
    if not enterprise:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ENTERPRISE_ACCESS_DENIED",
                "message": "Cette entreprise n'est pas accessible avec ce compte.",
            },
        )
    if membership.scope == "enterprise" and membership.enterprise_id != enterprise.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ENTERPRISE_SWITCH_FORBIDDEN",
                "message": "Ce collaborateur est affecté à une seule entreprise.",
            },
        )
    return membership, enterprise


def resolve_default_enterprise(
    db: Session,
    actor,
) -> tuple[EnterpriseMembership, Enterprise]:
    """Conserve le parcours historique tant que le mobile n'envoie pas de contexte."""
    membership = resolve_membership(db, actor)
    if membership.scope == "enterprise":
        requested_id = membership.enterprise_id
    else:
        primary = db.query(Enterprise.id).filter(
            Enterprise.group_id == membership.group_id,
            Enterprise.is_primary.is_(True),
            Enterprise.status == "active",
        ).first()
        requested_id = primary[0] if primary else None
    if not requested_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DEFAULT_ENTERPRISE_MISSING",
                "message": "Aucune entreprise active par défaut n'est disponible.",
            },
        )
    return resolve_active_enterprise(db, actor, requested_id)
