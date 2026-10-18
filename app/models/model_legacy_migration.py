from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from app.database import Base


class LegacyMigrationBatch(Base):
    __tablename__ = "legacy_migration_batches"
    __table_args__ = (Index("ix_legacy_migration_group_date", "group_id", "created_at"),)
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("enterprise_groups.id", ondelete="CASCADE"), nullable=False)
    source_enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=False)
    target_enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=False)
    status = Column(String(24), nullable=False, default="running")
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    report_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)


class LegacyMigrationItem(Base):
    __tablename__ = "legacy_migration_items"
    __table_args__ = (
        UniqueConstraint("source_depot_id", name="uq_legacy_migration_source_depot"),
        Index("ix_legacy_migration_item_batch", "batch_id"),
    )
    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("legacy_migration_batches.id", ondelete="CASCADE"), nullable=False)
    source_depot_id = Column(Integer, ForeignKey("depots.id"), nullable=False)
    target_laundry_order_id = Column(Integer, ForeignKey("laundry_orders.id"))
    target_client_id = Column(Integer, ForeignKey("clients.id"))
    status = Column(String(24), nullable=False)
    reason = Column(String(500))
    snapshot_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class LegacyClientMapping(Base):
    __tablename__ = "legacy_client_mappings"
    __table_args__ = (UniqueConstraint("source_client_id", "target_enterprise_id", name="uq_legacy_client_target"),)
    id = Column(Integer, primary_key=True)
    source_client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    target_client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    target_enterprise_id = Column(Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
