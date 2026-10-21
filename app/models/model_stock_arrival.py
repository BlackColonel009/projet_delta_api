from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class StockArrival(Base):
    __tablename__ = "stock_arrivals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'validated', 'cancelled')",
            name="ck_stock_arrivals_status",
        ),
        Index("ix_stock_arrivals_enterprise_created", "enterprise_id", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    enterprise_id = Column(
        Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("fournisseurs.id"), nullable=True)
    name = Column(String(180), nullable=False)
    reference = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="draft")
    created_by_name = Column(String(180), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    validated_at = Column(DateTime, nullable=True)

    enterprise = relationship("Enterprise")
    supplier = relationship("Fournisseur")
    lines = relationship(
        "StockArrivalLine",
        back_populates="arrival",
        cascade="all, delete-orphan",
        order_by="StockArrivalLine.id",
    )


class StockArrivalLine(Base):
    __tablename__ = "stock_arrival_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_stock_arrival_lines_quantity"),
        Index("ix_stock_arrival_lines_arrival_product", "arrival_id", "product_id"),
    )

    id = Column(Integer, primary_key=True)
    arrival_id = Column(
        Integer, ForeignKey("stock_arrivals.id", ondelete="CASCADE"), nullable=False
    )
    enterprise_id = Column(
        Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False
    )
    product_id = Column(
        Integer, ForeignKey("produits.id", ondelete="RESTRICT"), nullable=False
    )
    quantity = Column(Integer, nullable=False)
    barcodes_json = Column(JSON, nullable=False, default=list)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    arrival = relationship("StockArrival", back_populates="lines")
    product = relationship("Produit")
    units = relationship(
        "StockArrivalUnit", back_populates="line", cascade="all, delete-orphan"
    )


class StockArrivalUnit(Base):
    __tablename__ = "stock_arrival_units"
    __table_args__ = (
        Index("ix_stock_arrival_units_line", "arrival_line_id"),
        Index("ix_stock_arrival_units_unit", "unit_id", unique=True),
    )

    id = Column(Integer, primary_key=True)
    arrival_line_id = Column(
        Integer,
        ForeignKey("stock_arrival_lines.id", ondelete="CASCADE"),
        nullable=False,
    )
    unit_id = Column(
        Integer, ForeignKey("unites_produit.id", ondelete="RESTRICT"), nullable=False
    )
    barcode_snapshot = Column(String, nullable=True)
    traceability_snapshot = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    line = relationship("StockArrivalLine", back_populates="units")
    unit = relationship("UniteProduit")


class StockTransfer(Base):
    __tablename__ = "stock_transfers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('completed', 'cancelled')",
            name="ck_stock_transfers_status",
        ),
        Index("ix_stock_transfers_source_created", "source_enterprise_id", "created_at"),
        Index(
            "ix_stock_transfers_destination_created",
            "destination_enterprise_id",
            "created_at",
        ),
    )

    id = Column(Integer, primary_key=True)
    source_enterprise_id = Column(
        Integer, ForeignKey("enterprises.id", ondelete="RESTRICT"), nullable=False
    )
    destination_enterprise_id = Column(
        Integer, ForeignKey("enterprises.id", ondelete="RESTRICT"), nullable=False
    )
    source_arrival_id = Column(
        Integer, ForeignKey("stock_arrivals.id", ondelete="SET NULL"), nullable=True
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="completed")
    notes = Column(Text, nullable=True)
    created_by_name = Column(String(180), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    source_enterprise = relationship("Enterprise", foreign_keys=[source_enterprise_id])
    destination_enterprise = relationship(
        "Enterprise", foreign_keys=[destination_enterprise_id]
    )
    lines = relationship(
        "StockTransferLine", back_populates="transfer", cascade="all, delete-orphan"
    )


class StockTransferLine(Base):
    __tablename__ = "stock_transfer_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_stock_transfer_lines_quantity"),
    )

    id = Column(Integer, primary_key=True)
    transfer_id = Column(
        Integer, ForeignKey("stock_transfers.id", ondelete="CASCADE"), nullable=False
    )
    source_product_id = Column(
        Integer, ForeignKey("produits.id", ondelete="RESTRICT"), nullable=False
    )
    destination_product_id = Column(
        Integer, ForeignKey("produits.id", ondelete="RESTRICT"), nullable=False
    )
    quantity = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    transfer = relationship("StockTransfer", back_populates="lines")
    source_product = relationship("Produit", foreign_keys=[source_product_id])
    destination_product = relationship("Produit", foreign_keys=[destination_product_id])
    units = relationship(
        "StockTransferUnit", back_populates="line", cascade="all, delete-orphan"
    )


class StockTransferUnit(Base):
    __tablename__ = "stock_transfer_units"
    __table_args__ = (Index("ix_stock_transfer_units_line", "transfer_line_id"),)

    id = Column(Integer, primary_key=True)
    transfer_line_id = Column(
        Integer,
        ForeignKey("stock_transfer_lines.id", ondelete="CASCADE"),
        nullable=False,
    )
    unit_id = Column(
        Integer, ForeignKey("unites_produit.id", ondelete="RESTRICT"), nullable=False
    )
    barcode_snapshot = Column(String, nullable=True)
    traceability_snapshot = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    line = relationship("StockTransferLine", back_populates="units")
    unit = relationship("UniteProduit")
