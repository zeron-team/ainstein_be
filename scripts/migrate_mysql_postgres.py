
import os
import sys
import pymysql
import psycopg2
from psycopg2.extras import DictCursor

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def migrate():
    print("Connecting to databases...")
    # MySQL Connection (Source)
    # Using root/root for the temp container
    mysql_conn = pymysql.connect(
        host="127.0.0.1",
        port=3307,
        user="root",
        password="root",
        database="epc_db",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )

    # Postgres Connection (Target)
    pg_conn = psycopg2.connect(
        "postgresql://epc_user:epc_strong_pass_2025@localhost:5432/epc_db"
    )
    pg_conn.autocommit = False

    try:
        with mysql_conn.cursor() as mc, pg_conn.cursor() as pc:
            # 1. Roles
            print("Migrating Roles...")
            mc.execute("SELECT * FROM roles")
            roles = mc.fetchall()
            for r in roles:
                pc.execute(
                    "INSERT INTO roles (id, name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
                    (r['id'], r['name'])
                )
            
            # 2. Users (Handle bool conversion if needed)
            print("Migrating Users...")
            mc.execute("SELECT * FROM users")
            users = mc.fetchall()
            for u in users:
                pc.execute(
                    """
                    INSERT INTO users (id, username, password_hash, full_name, email, role_id, is_active, created_at, updated_at) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (u['id'], u['username'], u['password_hash'], u['full_name'], u['email'], 
                     u['role_id'], bool(u['is_active']), u['created_at'], u['updated_at'])
                )

            # 3. Branding
            print("Migrating Branding...")
            mc.execute("SELECT * FROM branding")
            branding = mc.fetchall()
            for b in branding:
                pc.execute(
                    """
                    INSERT INTO branding (id, hospital_nombre, logo_url, header_linea1, header_linea2, footer_linea1, footer_linea2, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (b['id'], b['hospital_nombre'], b['logo_url'], b['header_linea1'], b['header_linea2'],
                     b['footer_linea1'], b['footer_linea2'], b['updated_at'])
                )

            # 4. Patients
            print("Migrating Patients...")
            mc.execute("SELECT * FROM patients")
            patients = mc.fetchall()
            for p in patients:
                pc.execute(
                    """
                    INSERT INTO patients (id, dni, cuil, obra_social, nro_beneficiario, apellido, nombre, 
                    fecha_nacimiento, sexo, estado, telefono, email, domicilio, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (p['id'], p['dni'], p['cuil'], p['obra_social'], p['nro_beneficiario'], p['apellido'], p['nombre'],
                     p['fecha_nacimiento'], p['sexo'], p['estado'], p['telefono'], p['email'], p['domicilio'],
                     p['created_at'], p['updated_at'])
                )

            # 5. Patient Status
            print("Migrating Patient Status...")
            mc.execute("SELECT * FROM patient_status")
            statuses = mc.fetchall()
            for s in statuses:
                pc.execute(
                    """
                    INSERT INTO patient_status (patient_id, estado, observaciones, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (patient_id) DO NOTHING
                    """,
                    (s['patient_id'], s['estado'], s['observaciones'], s['updated_at'])
                )

            # 6. Admissions
            print("Migrating Admissions...")
            mc.execute("SELECT * FROM admissions")
            admissions = mc.fetchall()
            for a in admissions:
                pc.execute(
                    """
                    INSERT INTO admissions (id, patient_id, sector, habitacion, cama, fecha_ingreso, 
                    fecha_egreso, protocolo, admision_num, estado)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (a['id'], a['patient_id'], a['sector'], a['habitacion'], a['cama'], a['fecha_ingreso'],
                     a['fecha_egreso'], a['protocolo'], a['admision_num'], a['estado'] or 'internacion')
                )

            # 7. EPC
            print("Migrating EPC...")
            mc.execute("SELECT * FROM epc")
            epcs = mc.fetchall()
            for e in epcs:
                pc.execute(
                    """
                    INSERT INTO epc (id, patient_id, admission_id, estado, version_actual_oid, titulo, 
                    diagnostico_principal_cie10, fecha_emision, medico_responsable, firmado_por_medico, 
                    created_by, created_at, updated_at, 
                    motivo_internacion, evolucion, procedimientos, interconsultas, medicacion, indicaciones_alta, recomendaciones,
                    last_edited_by, last_edited_at, has_manual_changes, regenerated_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (e['id'], e['patient_id'], e['admission_id'], e['estado'], e['version_actual_oid'], e['titulo'],
                     e['diagnostico_principal_cie10'], e['fecha_emision'], e['medico_responsable'], bool(e['firmado_por_medico']),
                     e['created_by'], e['created_at'], e['updated_at'],
                     e['motivo_internacion'], e['evolucion'], e['procedimientos'], e['interconsultas'], e['medicacion'],
                     e['indicaciones_alta'], e['recomendaciones'],
                     e['last_edited_by'], e['last_edited_at'], bool(e['has_manual_changes']), e['regenerated_count'])
                )
            
            # 8. EPC Events
            print("Migrating EPC Events...")
            mc.execute("SELECT * FROM epc_events")
            events = mc.fetchall()
            for ev in events:
                pc.execute(
                    """
                    INSERT INTO epc_events (id, epc_id, at, by, action)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (ev['id'], ev['epc_id'], ev['at'], ev['by'], ev['action'])
                )
                # Update sequence if needed
                pc.execute(f"SELECT setval('epc_events_id_seq', {ev['id']})")


            print("Committing changes...")
            pg_conn.commit()
            print("Migration successful!")

    except Exception as e:
        pg_conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        mysql_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    migrate()
