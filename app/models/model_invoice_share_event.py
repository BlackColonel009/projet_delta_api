from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String

from app.database import Base


class InvoiceShareEvent(Base):
    __tablename__ = "invoice_share_events"
    __table_args__ = (
        Index(
            "ix_invoice_share_owner_created",
            "owner_user_id",
            "created_at",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=True)
    invoice_id = Column(
        Integer,
        ForeignKey("factures.id", ondelete="CASCADE"),
        nullable=False,
    )
    template = Column(String(24), nullable=False, default="simple")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
