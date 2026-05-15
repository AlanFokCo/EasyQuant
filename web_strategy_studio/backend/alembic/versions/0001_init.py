"""0001_init: Baseline schema (EasyQuant Web Studio Phase 0/1).

Revision ID: 0001_init
Revises:
Create Date: 2026-05-15 00:00:00.000000

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '0001_init'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'strategies',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('owner_id', sa.String(64), nullable=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('current_version', sa.Integer(), default=1, nullable=False),
        sa.Column('default_params', sa.JSON(), nullable=True),
    )

    op.create_table(
        'strategy_versions',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('strategy_id', sa.String(64), sa.ForeignKey('strategies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('source_code', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'runs',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('strategy_id', sa.String(64), sa.ForeignKey('strategies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('strategy_version', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(32), default='queued', nullable=False),
        sa.Column('progress', sa.Float(), default=0.0, nullable=False),
        sa.Column('stage', sa.String(64), nullable=True),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('error_code', sa.String(64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('html_path', sa.Text(), nullable=True),
        sa.Column('json_path', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('worker_hostname', sa.String(256), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('runs')
    op.drop_table('strategy_versions')
    op.drop_table('strategies')
