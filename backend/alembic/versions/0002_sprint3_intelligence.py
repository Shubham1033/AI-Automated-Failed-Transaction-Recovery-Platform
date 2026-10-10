"""Sprint 3 intelligence and promise-to-pay
Revision ID: 0002
"""
from alembic import op
import sqlalchemy as sa
revision='0002'; down_revision='0001'; branch_labels=None; depends_on=None

def upgrade():
    if sa.inspect(op.get_bind()).has_table('promise_to_pay'):
        return
    op.create_table('promise_to_pay',
        sa.Column('id',sa.String(64),primary_key=True),
        sa.Column('case_id',sa.String(64),sa.ForeignKey('recovery_cases.id'),nullable=False),
        sa.Column('promised_amount_paise',sa.Integer(),nullable=False),
        sa.Column('promised_date',sa.String(32),nullable=False),
        sa.Column('status',sa.String(50),nullable=False,server_default='pending'),
        sa.Column('source_message',sa.Text(),nullable=False),
        sa.Column('confidence',sa.Float(),nullable=False),
        sa.Column('created_at',sa.String(64),nullable=False),sa.Column('resolved_at',sa.String(64)))

def downgrade(): op.drop_table('promise_to_pay')
