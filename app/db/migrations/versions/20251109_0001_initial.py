from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import TINYINT, CHAR

# revision identifiers, used by Alembic.
revision = '20251109_0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('roles',
        sa.Column('id', TINYINT, primary_key=True),
        sa.Column('name', sa.String(20), nullable=False, unique=True)
    )

    op.create_table('users',
        sa.Column('id', CHAR(36), primary_key=True),
        sa.Column('username', sa.String(80), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(120), nullable=False),
        sa.Column('email', sa.String(120), unique=True),
        sa.Column('role_id', TINYINT, sa.ForeignKey('roles.id'), nullable=False),
        sa.Column('is_active', sa.Boolean, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=True)
    )

    op.create_table('patients',
        sa.Column('id', CHAR(36), primary_key=True),
        sa.Column('dni', sa.String(20)),
        sa.Column('cuil', sa.String(20)),
        sa.Column('obra_social', sa.String(80)),
        sa.Column('nro_beneficiario', sa.String(50)),
        sa.Column('apellido', sa.String(80), nullable=False),
        sa.Column('nombre', sa.String(80), nullable=False),
        sa.Column('fecha_nacimiento', sa.String(10)),
        sa.Column('sexo', sa.String(10)),
        sa.Column('telefono', sa.String(40)),
        sa.Column('email', sa.String(120)),
        sa.Column('domicilio', sa.Text()),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=True)
    )

    op.create_table('patient_status',
        sa.Column('patient_id', CHAR(36), sa.ForeignKey('patients.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('estado', sa.String(20), nullable=False),
        sa.Column('observaciones', sa.Text()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False)
    )

    op.create_table('admissions',
        sa.Column('id', CHAR(36), primary_key=True),
        sa.Column('patient_id', CHAR(36), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sector', sa.String(120)),
        sa.Column('habitacion', sa.String(40)),
        sa.Column('cama', sa.String(40)),
        sa.Column('fecha_ingreso', sa.DateTime, nullable=False),
        sa.Column('fecha_egreso', sa.DateTime),
        sa.Column('protocolo', sa.String(60)),
        sa.Column('admision_num', sa.String(60))
    )

    op.create_table('epc',
        sa.Column('id', CHAR(36), primary_key=True),
        sa.Column('patient_id', CHAR(36), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('admission_id', CHAR(36), sa.ForeignKey('admissions.id')),
        sa.Column('estado', sa.String(20), nullable=False),
        sa.Column('version_actual_oid', sa.String(64)),
        sa.Column('titulo', sa.String(255)),
        sa.Column('diagnostico_principal_cie10', sa.String(15)),
        sa.Column('fecha_emision', sa.DateTime),
        sa.Column('medico_responsable', sa.String(120)),
        sa.Column('firmado_por_medico', sa.Boolean, server_default=sa.text('0')),
        sa.Column('created_by', CHAR(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime)
    )

    op.create_table('branding',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('hospital_nombre', sa.String(160)),
        sa.Column('logo_url', sa.String(255)),
        sa.Column('header_linea1', sa.String(255)),
        sa.Column('header_linea2', sa.String(255)),
        sa.Column('footer_linea1', sa.String(255)),
        sa.Column('footer_linea2', sa.String(255)),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False)
    )

    op.execute("INSERT INTO roles(id,name) VALUES (1,'admin'),(2,'medico'),(3,'viewer')")
    op.execute("INSERT INTO branding(id,hospital_nombre) VALUES (1,'')")

def downgrade():
    op.drop_table('branding')
    op.drop_table('epc')
    op.drop_table('admissions')
    op.drop_table('patient_status')
    op.drop_table('patients')
    op.drop_table('users')
    op.drop_table('roles')
