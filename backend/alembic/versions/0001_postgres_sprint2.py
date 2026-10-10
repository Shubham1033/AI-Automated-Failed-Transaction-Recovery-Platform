"""Sprint 2 production schema

Revision ID: 0001
"""
from alembic import op
from app.schema import metadata
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    metadata.create_all(bind=bind)

def downgrade():
    bind = op.get_bind()
    metadata.drop_all(bind=bind)
