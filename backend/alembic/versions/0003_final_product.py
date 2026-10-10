"""Final product surfaces: communications
Revision ID: 0003
"""
from alembic import op
import sqlalchemy as sa
revision='0003'; down_revision='0002'; branch_labels=None; depends_on=None

def upgrade():
    inspector=sa.inspect(op.get_bind())
    if not inspector.has_table('recovery_communications'):
        op.create_table('recovery_communications',
            sa.Column('id',sa.String(64),primary_key=True),
            sa.Column('case_id',sa.String(64),sa.ForeignKey('recovery_cases.id'),nullable=False),
            sa.Column('channel',sa.String(32),nullable=False,server_default='email'),
            sa.Column('provider',sa.String(50),nullable=False),
            sa.Column('recipient',sa.String(255),nullable=False),
            sa.Column('subject',sa.String(255),nullable=False),
            sa.Column('body',sa.Text(),nullable=False),
            sa.Column('language',sa.String(32),nullable=False,server_default='hinglish'),
            sa.Column('status',sa.String(50),nullable=False),
            sa.Column('provider_message_id',sa.String(255)),
            sa.Column('payment_link',sa.Text()),
            sa.Column('created_at',sa.String(64),nullable=False),
            sa.Column('sent_at',sa.String(64)))

def downgrade():
    op.drop_table('recovery_communications')
