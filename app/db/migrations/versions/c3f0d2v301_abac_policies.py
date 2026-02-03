"""FERRO D2 v3.0.0: ABAC Policies Table

Revision ID: c3f0d2v301_abac_policies
Revises: c3f0d2v300_rls
Create Date: 2026-01-30

Creates the ABAC (Attribute-Based Access Control) policies table
for deterministic authorization decisions with audit logging.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 'c3f0d2v301_abac'
down_revision = 'c3f0d2v300_rls'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create ABAC policies and audit tables."""
    
    # ABAC Policies table
    op.create_table(
        'abac_policies',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=True),  # NULL = global policy
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('version', sa.Integer, nullable=False, default=1),
        sa.Column('is_active', sa.Boolean, nullable=False, default=True),
        sa.Column('strategy', sa.String(50), nullable=False, default='deny_overrides'),
        sa.Column('default_effect', sa.String(10), nullable=False, default='deny'),
        sa.Column('rules', JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('created_by', UUID(as_uuid=True), nullable=True),
    )
    
    # Unique constraint: one active policy per tenant+name
    op.create_index(
        'idx_abac_policies_tenant_name_active',
        'abac_policies',
        ['tenant_id', 'name'],
        unique=True,
        postgresql_where=sa.text('is_active = true')
    )
    
    # ABAC Decision Audit Log
    op.create_table(
        'abac_audit_log',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('trace_id', sa.String(64), nullable=False, index=True),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('resource_id', sa.String(255), nullable=True),
        sa.Column('effect', sa.String(10), nullable=False),  # allow/deny
        sa.Column('matched_rules', JSONB, nullable=False),  # Array of rule IDs that matched
        sa.Column('policy_version', sa.Integer, nullable=False),
        sa.Column('context', JSONB, nullable=True),  # Additional context (sanitized)
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), index=True),
    )
    
    # Enable RLS on ABAC tables
    op.execute("ALTER TABLE abac_policies ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY rls_abac_policies_tenant ON abac_policies
        USING (
            tenant_id IS NULL 
            OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        );
    """)
    
    op.execute("ALTER TABLE abac_audit_log ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY rls_abac_audit_tenant ON abac_audit_log
        USING (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        );
    """)


def downgrade() -> None:
    """Drop ABAC tables."""
    op.execute("DROP POLICY IF EXISTS rls_abac_audit_tenant ON abac_audit_log;")
    op.execute("DROP POLICY IF EXISTS rls_abac_policies_tenant ON abac_policies;")
    op.drop_table('abac_audit_log')
    op.drop_table('abac_policies')
