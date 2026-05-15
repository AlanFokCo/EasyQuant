"""0002_phase2: Add content_hash and label to strategy_versions (B4/B15).

Revision ID: 0002_phase2
Revises: 0001_init
Create Date: 2026-05-15 00:00:01.000000

"""
import sqlalchemy as sa

from alembic import op

revision = '0002_phase2'
down_revision = '0001_init'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # B4/B15: content_hash enables deduplication on PATCH.
    # Nullable because existing rows do not have a hash; computed on first write.
    op.add_column(
        'strategy_versions',
        sa.Column('content_hash', sa.String(64), nullable=True),
    )
    # Named snapshot label (set by POST /strategies/{id}/snapshot).
    op.add_column(
        'strategy_versions',
        sa.Column('label', sa.String(256), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('strategy_versions', 'label')
    op.drop_column('strategy_versions', 'content_hash')
