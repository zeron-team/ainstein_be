# app/scripts/bootstrap_admin.py
import os, uuid, sys
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.repositories.user_repo import UserRepo
from app.core.security import hash_password
from sqlalchemy import text

def ensure_roles(db: Session):
    # por si la revisión inicial no insertó roles
    db.execute(text(
        "INSERT IGNORE INTO roles(id,name) VALUES (1,'admin'),(2,'medico'),(3,'viewer')"
    ))
    db.commit()

def main():
    username = os.getenv("ADMIN_USER", "admin")
    password = os.getenv("ADMIN_PASS", "Admin.1234")
    full_name = os.getenv("ADMIN_NAME", "Administrador")
    email = os.getenv("ADMIN_EMAIL", "admin@example.com")

    db = SessionLocal()
    try:
        ensure_roles(db)
        repo = UserRepo(db)
        u = repo.get_by_username(username)
        if u:
            print(f"[ok] Usuario '{username}' ya existe.")
            return 0
        user_id = str(uuid.uuid4())
        repo.create(
            id=user_id,
            username=username,
            password_hash=hash_password(password),
            full_name=full_name,
            email=email,
            role_id=1,    # admin
            is_active=True,
        )
        print(f"[ok] Admin creado: {username} / (pass oculto)  id={user_id}")
        return 0
    finally:
        db.close()

if __name__ == "__main__":
    sys.exit(main())