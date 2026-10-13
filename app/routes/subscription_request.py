from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.mail import send_email_message
from app.database import get_db
from app.email.branded_templates import (
    subscription_request_admin_email,
    subscription_request_decision_email,
)
from app.models.model_notification import Notification
from app.models.model_souscription import Subscription
from app.models.model_subscription_plan import SubscriptionPlan
from app.models.model_subscription_request import SubscriptionChangeRequest
from app.models.model_user import User
from app.schemas.subscription_request_schema import (
    SubscriptionChangeRequestCreate,
    SubscriptionChangeRequestReview,
)
from app.services.subscription_service import activate_subscription
from app.utils.security import get_active_user, require_main_user, require_super_user


router = APIRouter(prefix="/subscriptions/requests", tags=["Subscription Requests"])


def _owner_id(current_user) -> int:
    return current_user.id if current_user.is_main_user else current_user.parent_user_id


def _latest_plan_code(db: Session, user_id: int) -> str | None:
    subscription = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc(), Subscription.id.desc())
        .first()
    )
    return subscription.plan_code if subscription else None


def _payload(item: SubscriptionChangeRequest):
    user = item.user
    plan = item.requested_plan
    return {
        "id": item.id,
        "user_id": item.user_id,
        "company_name": user.societe_ou_entreprise if user else None,
        "email": user.email if user else None,
        "current_plan_code": item.current_plan_code,
        "requested_plan_code": item.requested_plan_code,
        "requested_plan_name": plan.name if plan else item.requested_plan_code,
        "billing_cycle": item.billing_cycle,
        "quoted_amount": item.quoted_amount,
        "currency": item.currency,
        "status": item.status,
        "note": item.note,
        "admin_note": item.admin_note,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "reviewed_at": item.reviewed_at,
    }


def _billing_label(cycle: str) -> str:
    return "annuelle" if cycle == "annual" else "mensuelle"


def _format_amount(value: float, currency: str) -> str:
    return f"{float(value or 0):,.0f}".replace(",", " ") + f" {currency}"


def _notify_superadmins(
    db: Session,
    *,
    request: SubscriptionChangeRequest,
    company: User,
    plan: SubscriptionPlan,
) -> list[User]:
    admins = db.query(User).filter(User.is_superuser.is_(True)).all()
    company_name = company.societe_ou_entreprise or company.email
    message = (
        f"{company_name} demande l’offre {plan.name} en facturation "
        f"{_billing_label(request.billing_cycle)} pour "
        f"{_format_amount(request.quoted_amount, request.currency)}."
    )
    if request.note:
        message += f" Message : {request.note.strip()}"
    for admin in admins:
        db.add(
            Notification(
                titre="Nouvelle demande de mise à niveau",
                message=message,
                user_id=company.id,
                parent_user_id=admin.id,
                is_read=False,
            )
        )
    return admins


def _notify_company_decision(
    db: Session,
    *,
    request: SubscriptionChangeRequest,
    plan: SubscriptionPlan,
    approved: bool,
) -> None:
    status = "approuvée" if approved else "refusée"
    message = f"Votre demande pour l’offre {plan.name} a été {status}."
    if request.admin_note:
        message += f" Réponse : {request.admin_note.strip()}"
    db.add(
        Notification(
            titre=f"Demande d’abonnement {status}",
            message=message,
            parent_user_id=request.user_id,
            is_read=False,
        )
    )


@router.post("")
def create_request(
    payload: SubscriptionChangeRequestCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_main_user),
    db: Session = Depends(get_db),
):
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.code == payload.plan_code,
        SubscriptionPlan.is_active.is_(True),
    ).first()
    if not plan:
        raise HTTPException(404, "Offre introuvable ou indisponible")

    pending = db.query(SubscriptionChangeRequest).filter(
        SubscriptionChangeRequest.user_id == current_user.id,
        SubscriptionChangeRequest.status == "pending",
    ).first()
    if pending:
        raise HTTPException(
            409,
            "Une demande est déjà en attente. Annulez-la avant d’en créer une autre.",
        )

    current_plan_code = _latest_plan_code(db, current_user.id)
    if current_plan_code == plan.code:
        raise HTTPException(400, "Cette offre est déjà active pour votre entreprise")

    cycle = payload.billing_cycle.value
    request = SubscriptionChangeRequest(
        user_id=current_user.id,
        current_plan_code=current_plan_code,
        requested_plan_code=plan.code,
        billing_cycle=cycle,
        quoted_amount=plan.annual_price if cycle == "annual" else plan.monthly_price,
        currency=plan.currency,
        note=payload.note.strip() if payload.note else None,
    )
    db.add(request)
    admins = _notify_superadmins(
        db,
        request=request,
        company=current_user,
        plan=plan,
    )
    db.commit()
    db.refresh(request)
    for admin in admins:
        if admin.email:
            email_body = subscription_request_admin_email(
                requester=current_user,
                plan=plan,
                request=request,
                recipient=admin,
            )
            background_tasks.add_task(
                send_email_message,
                to_email=admin.email,
                subject=(
                    f"New subscription request — {current_user.societe_ou_entreprise or current_user.email}"
                    if admin.interface_language == "en"
                    else f"Nouvelle demande d’abonnement — {current_user.societe_ou_entreprise or current_user.email}"
                ),
                body=email_body,
                is_html=True,
                reply_to=current_user.email,
            )
    return _payload(request)


@router.get("/mine")
def list_my_requests(
    current_user=Depends(get_active_user),
    db: Session = Depends(get_db),
):
    items = db.query(SubscriptionChangeRequest).filter(
        SubscriptionChangeRequest.user_id == _owner_id(current_user),
    ).order_by(SubscriptionChangeRequest.created_at.desc()).all()
    return [_payload(item) for item in items]


@router.post("/{request_id}/cancel")
def cancel_request(
    request_id: int,
    current_user: User = Depends(require_main_user),
    db: Session = Depends(get_db),
):
    item = db.query(SubscriptionChangeRequest).filter(
        SubscriptionChangeRequest.id == request_id,
        SubscriptionChangeRequest.user_id == current_user.id,
    ).first()
    if not item:
        raise HTTPException(404, "Demande introuvable")
    if item.status != "pending":
        raise HTTPException(409, "Seule une demande en attente peut être annulée")
    item.status = "cancelled"
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return _payload(item)


@router.get("/admin")
def list_requests_for_admin(
    status: str | None = Query(default=None, pattern="^(pending|approved|rejected|cancelled)$"),
    _: User = Depends(require_super_user),
    db: Session = Depends(get_db),
):
    query = db.query(SubscriptionChangeRequest)
    if status:
        query = query.filter(SubscriptionChangeRequest.status == status)
    return [_payload(item) for item in query.order_by(SubscriptionChangeRequest.created_at.desc()).all()]


@router.post("/{request_id}/approve")
def approve_request(
    request_id: int,
    payload: SubscriptionChangeRequestReview,
    background_tasks: BackgroundTasks,
    reviewer: User = Depends(require_super_user),
    db: Session = Depends(get_db),
):
    item = db.query(SubscriptionChangeRequest).filter(
        SubscriptionChangeRequest.id == request_id,
    ).with_for_update().first()
    if not item:
        raise HTTPException(404, "Demande introuvable")
    if item.status != "pending":
        raise HTTPException(409, "Cette demande a déjà été traitée")
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.code == item.requested_plan_code,
        SubscriptionPlan.is_active.is_(True),
    ).first()
    if not plan:
        raise HTTPException(409, "L’offre demandée n’est plus disponible")

    subscription = activate_subscription(
        db,
        user_id=item.user_id,
        plan=plan,
        billing_cycle=item.billing_cycle,
        granted_by_admin=True,
    )
    now = datetime.utcnow()
    item.status = "approved"
    item.admin_note = payload.admin_note.strip() if payload.admin_note else None
    item.reviewed_by_user_id = reviewer.id
    item.reviewed_at = now
    item.updated_at = now
    _notify_company_decision(db, request=item, plan=plan, approved=True)
    db.commit()
    db.refresh(item)
    company = item.user
    if company and company.email:
        background_tasks.add_task(
            send_email_message,
            to_email=company.email,
            subject=(
                f"Your request for the {plan.name} plan was approved"
                if company.interface_language == "en"
                else f"Votre demande pour l’offre {plan.name} a été approuvée"
            ),
            body=subscription_request_decision_email(
                company=company,
                plan=plan,
                request=item,
                approved=True,
            ),
            is_html=True,
        )
    return {"request": _payload(item), "subscription_id": subscription.id}


@router.post("/{request_id}/reject")
def reject_request(
    request_id: int,
    payload: SubscriptionChangeRequestReview,
    background_tasks: BackgroundTasks,
    reviewer: User = Depends(require_super_user),
    db: Session = Depends(get_db),
):
    item = db.query(SubscriptionChangeRequest).filter(
        SubscriptionChangeRequest.id == request_id,
    ).with_for_update().first()
    if not item:
        raise HTTPException(404, "Demande introuvable")
    if item.status != "pending":
        raise HTTPException(409, "Cette demande a déjà été traitée")
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.code == item.requested_plan_code,
    ).first()
    if not plan:
        raise HTTPException(409, "L’offre demandée n’est plus disponible")
    now = datetime.utcnow()
    item.status = "rejected"
    item.admin_note = payload.admin_note.strip() if payload.admin_note else None
    item.reviewed_by_user_id = reviewer.id
    item.reviewed_at = now
    item.updated_at = now
    _notify_company_decision(db, request=item, plan=plan, approved=False)
    db.commit()
    db.refresh(item)
    company = item.user
    if company and company.email:
        background_tasks.add_task(
            send_email_message,
            to_email=company.email,
            subject=(
                f"Response to your request for the {plan.name} plan"
                if company.interface_language == "en"
                else f"Réponse à votre demande pour l’offre {plan.name}"
            ),
            body=subscription_request_decision_email(
                company=company,
                plan=plan,
                request=item,
                approved=False,
            ),
            is_html=True,
        )
    return _payload(item)
