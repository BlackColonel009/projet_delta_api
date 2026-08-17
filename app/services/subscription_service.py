from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.model_souscription import Subscription

def create_trial_subscription(db: Session, user_id: int):
    subscription = Subscription(
        user_id=user_id,
        type="trial",
        status="active",
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        granted_by_admin=False
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription
