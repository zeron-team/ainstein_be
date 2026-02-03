"""FERRO D2 v3.0.0: RLS Multi-Tenant Security

Revision ID: c3f0d2v300_rls_multitenant
Revises: a8f4008b2bf0
Create Date: 2026-01-30

This migration enables Row Level Security (RLS) for multi-tenant isolation.
All tables with tenant_id get RLS policies that filter by app.tenant_id GUC.

FERRO D2 Rules:
- All multi-tenant tables MUST have tenant_id NOT NULL
- RLS ENABLED on all critical tables
- Middleware sets SET LOCAL app.tenant_id per request
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'c3f0d2v300_rls'
down_revision = 'a8f4008b2bf0'
branch_labels = None
depends_on = None


# Tables that require RLS (those with tenant_id column)
RLS_TABLES = [
    'users',
    'patients', 
    'hces',
    'epcs',
    'epc_audits',
    'pdf_templates',
]


def upgrade() -> None:
    """Enable RLS on multi-tenant tables."""
    
    # Create the GUC settings if not exists (for app.tenant_id and app.user_id)
    # These are set per-session via SET LOCAL
    
    for table in RLS_TABLES:
        # Check if table exists before enabling RLS
        op.execute(f"""
            DO $$
            BEGIN
                -- Enable RLS on table
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table}') THEN
                    EXECUTE 'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY';
                    
                    -- Drop existing policy if exists (for idempotency)
                    EXECUTE 'DROP POLICY IF EXISTS rls_{table}_tenant ON {table}';
                    
                    -- Create tenant isolation policy
                    -- Policy uses current_setting which returns empty string if not set
                    EXECUTE '
                        CREATE POLICY rls_{table}_tenant ON {table}
                        USING (
                            tenant_id IS NULL 
                            OR tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')
                        )
                    ';
                    
                    RAISE NOTICE 'RLS enabled on table: {table}';
                ELSE
                    RAISE NOTICE 'Table {table} does not exist, skipping RLS';
                END IF;
            END
            $$;
        """)
    
    # Create index on tenant_id for performance (if not exists)
    for table in RLS_TABLES:
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table}')
                   AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = '{table}' AND column_name = 'tenant_id')
                   AND NOT EXISTS (SELECT 1 FROM pg_indexes WHERE tablename = '{table}' AND indexname = 'idx_{table}_tenant_id')
                THEN
                    EXECUTE 'CREATE INDEX idx_{table}_tenant_id ON {table}(tenant_id)';
                END IF;
            END
            $$;
        """)


def downgrade() -> None:
    """Disable RLS on multi-tenant tables."""
    
    for table in RLS_TABLES:
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table}') THEN
                    -- Drop the policy
                    EXECUTE 'DROP POLICY IF EXISTS rls_{table}_tenant ON {table}';
                    
                    -- Disable RLS
                    EXECUTE 'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY';
                    
                    RAISE NOTICE 'RLS disabled on table: {table}';
                END IF;
            END
            $$;
        """)
