#!/usr/bin/env python3
"""
Script para restaurar datos desde MySQL dump a PostgreSQL.
Lee el dump MySQL y extrae los inserts para cada tabla.
"""

import re
import subprocess

TENANT_ID = "00000000-0000-0000-0000-000000000001"
DUMP_FILE = "/home/ubuntu/ainstein/ainstein_be/dumps_20260128/mysql_epc_db.sql"

def run_psql(sql: str) -> tuple[bool, str]:
    """Ejecuta SQL en PostgreSQL via docker."""
    cmd = [
        "docker", "exec", "-i", "ferro_postgres", 
        "psql", "-U", "epc_user", "-d", "epc_db"
    ]
    result = subprocess.run(cmd, input=sql, capture_output=True, text=True)
    return result.returncode == 0, result.stdout + result.stderr

def extract_values(dump_content: str, table_name: str) -> str | None:
    """Extrae los VALUES del INSERT de una tabla específica."""
    pattern = rf"INSERT INTO `{table_name}` VALUES (.*);"
    match = re.search(pattern, dump_content, re.DOTALL)
    if match:
        return match.group(1)
    return None

def main():
    with open(DUMP_FILE, 'r', encoding='utf-8') as f:
        dump = f.read()
    
    # 1. Insert Tenant
    print("📦 Insertando tenant...")
    sql = f"""
    INSERT INTO tenants (id, code, name, is_active, created_at, integration_type)
    VALUES ('{TENANT_ID}', 'markey', 'Clinica Markey', TRUE, NOW(), 'inbound')
    ON CONFLICT (id) DO NOTHING;
    """
    ok, out = run_psql(sql)
    print(f"  {'✅' if ok else '❌'} Tenant: {out.strip() if not ok else 'OK'}")
    
    # 2. Insert Roles
    print("📦 Insertando roles...")
    sql = """
    INSERT INTO roles (id, name) VALUES (1, 'admin') ON CONFLICT DO NOTHING;
    INSERT INTO roles (id, name) VALUES (2, 'medico') ON CONFLICT DO NOTHING;
    INSERT INTO roles (id, name) VALUES (3, 'viewer') ON CONFLICT DO NOTHING;
    """
    ok, out = run_psql(sql)
    print(f"  {'✅' if ok else '❌'} Roles")
    
    # 3. Insert Users
    print("📦 Insertando users...")
    users_values = extract_values(dump, 'users')
    if users_values:
        # Convertir tinyint(1) a boolean y agregar tenant_id
        rows = re.findall(r"\(([^)]+)\)", users_values)
        for row in rows:
            # Parse row: id, username, password_hash, full_name, email, role_id, is_active, created_at, updated_at
            parts = row.split(",", 8)
            if len(parts) >= 7:
                user_id = parts[0].strip()
                username = parts[1].strip()
                password_hash = parts[2].strip()
                full_name = parts[3].strip()
                email = parts[4].strip()
                role_id = parts[5].strip()
                is_active = 'TRUE' if parts[6].strip() == '1' else 'FALSE'
                created_at = parts[7].strip() if len(parts) > 7 else 'NOW()'
                updated_at = parts[8].strip() if len(parts) > 8 else 'NULL'
                
                sql = f"""
                INSERT INTO users (id, username, password_hash, full_name, email, role_id, is_active, created_at, updated_at, tenant_id)
                VALUES ({user_id}, {username}, {password_hash}, {full_name}, {email}, {role_id}, {is_active}, {created_at}, {updated_at}, '{TENANT_ID}')
                ON CONFLICT (id) DO NOTHING;
                """
                ok, out = run_psql(sql)
                if not ok:
                    print(f"    ⚠️ User {username}: {out.strip()[:80]}")
        print("  ✅ Users importados")
    
    # 4. Insert Patients
    print("📦 Insertando patients...")
    patients_values = extract_values(dump, 'patients')
    if patients_values:
        rows = re.findall(r"\(([^)]+)\)", patients_values)
        count = 0
        for row in rows:
            parts = row.split(",", 12)
            if len(parts) >= 9:
                patient_id = parts[0].strip()
                dni = parts[1].strip()
                cuil = parts[2].strip()
                obra_social = parts[3].strip()
                nro_beneficiario = parts[4].strip()
                apellido = parts[5].strip()
                nombre = parts[6].strip()
                fecha_nac = parts[7].strip()
                sexo = parts[8].strip()
                telefono = parts[9].strip() if len(parts) > 9 else 'NULL'
                email = parts[10].strip() if len(parts) > 10 else 'NULL'
                domicilio = parts[11].strip() if len(parts) > 11 else 'NULL'
                estado = parts[12].strip() if len(parts) > 12 else 'NULL'
                created_at = parts[13].strip() if len(parts) > 13 else 'NOW()'
                
                sql = f"""
                INSERT INTO patients (id, dni, cuil, obra_social, nro_beneficiario, apellido, nombre, fecha_nacimiento, sexo, telefono, email, domicilio, estado, created_at, tenant_id)
                VALUES ({patient_id}, {dni}, {cuil}, {obra_social}, {nro_beneficiario}, {apellido}, {nombre}, {fecha_nac}, {sexo}, {telefono}, {email}, {domicilio}, {estado}, NOW(), '{TENANT_ID}')
                ON CONFLICT (id) DO NOTHING;
                """
                ok, out = run_psql(sql)
                if ok:
                    count += 1
        print(f"  ✅ {count} patients importados")

    # 5. Insert Patient Status
    print("📦 Insertando patient_status...")
    ps_values = extract_values(dump, 'patient_status')
    if ps_values:
        rows = re.findall(r"\(([^)]+)\)", ps_values)
        count = 0
        for row in rows:
            parts = row.split(",", 3)
            if len(parts) >= 3:
                patient_id = parts[0].strip()
                estado = parts[1].strip()
                observaciones = parts[2].strip().replace("\\'", "''")
                
                sql = f"""
                INSERT INTO patient_status (patient_id, estado, observaciones, updated_at)
                VALUES ({patient_id}, {estado}, {observaciones}, NOW())
                ON CONFLICT (patient_id) DO NOTHING;
                """
                ok, out = run_psql(sql)
                if ok:
                    count += 1
        print(f"  ✅ {count} patient_status importados")

    # 6. Insert Admissions
    print("📦 Insertando admissions...")
    adm_values = extract_values(dump, 'admissions')
    if adm_values:
        rows = re.findall(r"\(([^)]+)\)", adm_values)
        count = 0
        for row in rows:
            parts = row.split(",", 9)
            if len(parts) >= 6:
                adm_id = parts[0].strip()
                patient_id = parts[1].strip()
                sector = parts[2].strip()
                habitacion = parts[3].strip()
                cama = parts[4].strip()
                fecha_ingreso = parts[5].strip()
                fecha_egreso = parts[6].strip() if len(parts) > 6 else 'NULL'
                protocolo = parts[7].strip() if len(parts) > 7 else 'NULL'
                admision_num = parts[8].strip() if len(parts) > 8 else 'NULL'
                estado = parts[9].strip() if len(parts) > 9 else 'NULL'
                
                sql = f"""
                INSERT INTO admissions (id, patient_id, sector, habitacion, cama, fecha_ingreso, fecha_egreso, protocolo, admision_num, estado, tenant_id)
                VALUES ({adm_id}, {patient_id}, {sector}, {habitacion}, {cama}, {fecha_ingreso}, {fecha_egreso}, {protocolo}, {admision_num}, {estado}, '{TENANT_ID}')
                ON CONFLICT (id) DO NOTHING;
                """
                ok, out = run_psql(sql)
                if ok:
                    count += 1
        print(f"  ✅ {count} admissions importados")

    # 7. Insert EPC Events
    print("📦 Insertando epc_events...")
    events_values = extract_values(dump, 'epc_events')
    if events_values:
        rows = re.findall(r"\(([^)]+)\)", events_values)
        count = 0
        for row in rows:
            parts = row.split(",", 4)
            if len(parts) >= 5:
                event_id = parts[0].strip()
                epc_id = parts[1].strip()
                at_time = parts[2].strip()
                by_user = parts[3].strip()
                action = parts[4].strip()
                
                sql = f"""
                INSERT INTO epc_events (id, epc_id, at, "by", action)
                VALUES ({event_id}, {epc_id}, {at_time}, {by_user}, {action})
                ON CONFLICT (id) DO NOTHING;
                """
                ok, out = run_psql(sql)
                if ok:
                    count += 1
        print(f"  ✅ {count} epc_events importados")

    # 8. Insert branding
    print("📦 Insertando branding...")
    sql = f"""
    INSERT INTO branding (id, hospital_nombre, tenant_id, updated_at)
    VALUES (1, 'Clínica Markey', '{TENANT_ID}', NOW())
    ON CONFLICT (id) DO NOTHING;
    """
    ok, out = run_psql(sql)
    print(f"  {'✅' if ok else '❌'} Branding")

    print("\n🎉 Restauración PostgreSQL completada!")

if __name__ == "__main__":
    main()
