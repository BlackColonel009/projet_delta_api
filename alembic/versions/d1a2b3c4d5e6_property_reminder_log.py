"""property reminder delivery log"""
from alembic import op
import sqlalchemy as sa
revision="d1a2b3c4d5e6";down_revision="c0f1a2b3c4d5";branch_labels=None;depends_on=None


def upgrade():
    op.create_table("property_reminder_logs",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("enterprise_id",sa.Integer(),sa.ForeignKey("enterprises.id",ondelete="CASCADE"),nullable=False),sa.Column("due_id",sa.Integer(),sa.ForeignKey("property_payment_dues.id",ondelete="CASCADE"),nullable=False),sa.Column("channel",sa.String(20),nullable=False),sa.Column("reminder_key",sa.String(80),nullable=False),sa.Column("status",sa.String(20),nullable=False,server_default="sent"),sa.Column("error_message",sa.String(500)),sa.Column("created_at",sa.DateTime(),nullable=False),sa.UniqueConstraint("due_id","channel","reminder_key",name="uq_property_reminder_delivery"))
    op.create_index("ix_property_reminder_enterprise_date","property_reminder_logs",["enterprise_id","created_at"])


def downgrade():op.drop_table("property_reminder_logs")
