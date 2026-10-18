from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class EnterpriseGroup(Base):
    __tablename__ = "enterprise_groups"

    id = Column(Integer, primary_key=True)
    owner_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    name = Column(String(160), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    owner = relationship("User", foreign_keys=[owner_user_id])
    enterprises = relationship(
        "Enterprise",
        back_populates="group",
        cascade="all, delete-orphan",
    )


class Enterprise(Base):
    __tablename__ = "enterprises"
    __table_args__ = (
        UniqueConstraint("group_id", "code", name="uq_enterprises_group_code"),
        CheckConstraint(
            "enterprise_type IN ('principale', 'standard', 'consigne')",
            name="ck_enterprises_type",
        ),
        CheckConstraint(
            "business_type IN ('commerce', 'laundry', 'vehicle_rental', "
            "'property_rental', 'legacy_consignment')",
            name="ck_enterprises_business_type",
        ),
        Index(
            "uq_enterprises_one_primary_per_group",
            "group_id",
            unique=True,
            postgresql_where=text("is_primary IS TRUE"),
            sqlite_where=text("is_primary = 1"),
        ),
        Index("ix_enterprises_group_status", "group_id", "status"),
    )

    id = Column(Integer, primary_key=True)
    group_id = Column(
        Integer,
        ForeignKey("enterprise_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(160), nullable=False)
    code = Column(String(80), nullable=False)
    is_primary = Column(Boolean, nullable=False, default=False)
    enterprise_type = Column(String(32), nullable=False, default="standard")
    business_type = Column(String(40), nullable=False, default="commerce")
    status = Column(String(24), nullable=False, default="active")
    address = Column(String, nullable=True)
    phone = Column(String(40), nullable=True)
    email = Column(String(255), nullable=True)
    logo_url = Column(String, nullable=True)
    app_theme = Column(String(32), nullable=False, default="tradecare")
    theme_mode = Column(String(16), nullable=False, default="system")
    invoice_color = Column(String(16), nullable=False, default="#5C6BC0")
    simple_invoice_template = Column(
        String(48), nullable=False, default="simple_classic"
    )
    professional_invoice_template = Column(
        String(48), nullable=False, default="professional_signature"
    )
    show_invoice_agent = Column(Boolean, nullable=False, default=True)
    currency = Column(String(10), nullable=False, default="XOF")
    timezone = Column(String(64), nullable=False, default="Africa/Lome")
    automatic_work_report_enabled = Column(Boolean, nullable=False, default=False)
    automatic_work_report_inherit_time = Column(Boolean, nullable=False, default=True)
    automatic_work_report_hour = Column(Integer, nullable=False, default=18)
    automatic_work_report_minute = Column(Integer, nullable=False, default=0)
    automatic_work_report_config = Column(JSON, nullable=False, default=dict)
    map_position_x = Column(Float, nullable=True)
    map_position_y = Column(Float, nullable=True)
    map_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    group = relationship("EnterpriseGroup", back_populates="enterprises")
    service_profiles = relationship(
        "EnterpriseServiceProfile",
        back_populates="enterprise",
        cascade="all, delete-orphan",
    )


class EnterpriseServiceProfile(Base):
    __tablename__ = "enterprise_service_profiles"
    __table_args__ = (
        UniqueConstraint(
            "enterprise_id",
            "service_code",
            name="uq_enterprise_service_profiles_code",
        ),
    )

    id = Column(Integer, primary_key=True)
    enterprise_id = Column(
        Integer,
        ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_code = Column(String(48), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    configuration_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    enterprise = relationship("Enterprise", back_populates="service_profiles")


class EnterpriseMembership(Base):
    __tablename__ = "enterprise_memberships"
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL AND sub_user_id IS NULL) OR "
            "(user_id IS NULL AND sub_user_id IS NOT NULL)",
            name="ck_enterprise_memberships_one_actor",
        ),
        CheckConstraint(
            "(scope = 'group' AND enterprise_id IS NULL) OR "
            "(scope = 'enterprise' AND enterprise_id IS NOT NULL)",
            name="ck_enterprise_memberships_scope_target",
        ),
        UniqueConstraint(
            "user_id",
            "group_id",
            "scope",
            name="uq_enterprise_memberships_user_scope",
        ),
        UniqueConstraint(
            "sub_user_id",
            "group_id",
            "scope",
            name="uq_enterprise_memberships_sub_scope",
        ),
        Index("ix_enterprise_memberships_group_active", "group_id", "is_active"),
        Index(
            "ix_enterprise_memberships_enterprise_active",
            "enterprise_id",
            "is_active",
        ),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    sub_user_id = Column(
        Integer,
        ForeignKey("sub_users.id", ondelete="CASCADE"),
        nullable=True,
    )
    group_id = Column(
        Integer,
        ForeignKey("enterprise_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    enterprise_id = Column(
        Integer,
        ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=True,
    )
    role = Column(String(48), nullable=False)
    scope = Column(String(16), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    group = relationship("EnterpriseGroup")
    enterprise = relationship("Enterprise")
    user = relationship("User", foreign_keys=[user_id])
    sub_user = relationship("SubUser", foreign_keys=[sub_user_id])
