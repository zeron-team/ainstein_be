#!/usr/bin/env python
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

# Ajustá estos imports si en tu proyecto cambian los paths
from app.db.session import SessionLocal
from app.domain.models import User, Role

# 👇 Importamos el mismo contexto de passwords que usa tu auth
from app.core.security import pwd_context


def hash_password(password: str) -> str:
    """
    Usa el mismo pwd_context que el login para hashear contraseñas.
    Así te asegurás que el usuario que creamos pueda loguear bien.
    """
    return pwd_context.hash(password)


def ensure_roles(db: Session) -> dict[str, Role]:
    """
    Crea los roles básicos si no existen y los devuelve en un dict.
    """
    role_names = ["admin", "medico", "viewer"]
    roles: dict[str, Role] = {}

    for name in role_names:
        role = db.query(Role).filter(Role.name == name).one_or_none()
        if not role:
            role = Role(name=name)
            db.add(role)
            db.commit()
            db.refresh(role)
            print(f"[INFO] Rol creado: {name} (id={role.id})")
        else:
            print(f"[INFO] Rol existente: {name} (id={role.id})")
        roles[name] = role

    return roles


def create_admin_user(
    db: Session,
    username: str,
    password: str,
    email: str,
    full_name: str = "Administrador General",
):
    """
    Crea un usuario admin si no existe.
    """
    existing = db.query(User).filter(User.username == username).one_or_none()
    if existing:
        print(f"[WARN] Ya existe un usuario con username='{username}'. No se crea otro.")
        return

    roles = ensure_roles(db)
    admin_role = roles["admin"]

    pwd_hash = hash_password(password)

    user = User(
        id=str(uuid.uuid4()),
        username=username,
        password_hash=pwd_hash,
        full_name=full_name,
        email=email,
        role_id=admin_role.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    print("===============================================")
    print("[OK] Usuario admin creado correctamente:")
    print(f"  Username: {username}")
    print(f"  Email:    {email}")
    print(f"  Rol:      admin")
    print("  IMPORTANTE: Guardá bien esta contraseña:")
    print(f"  Password: {password}")
    print("===============================================")


def main():
    # 🔐 Podés cambiar estos valores a gusto
    username = "admin"
    password = "Admin123!"
    email = "admin@example.com"

    db = SessionLocal()
    try:
        create_admin_user(db, username=username, password=password, email=email)
    finally:
        db.close()


if __name__ == "__main__":
    main()