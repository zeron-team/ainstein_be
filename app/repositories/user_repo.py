# app/repositories/user_repo.py
from __future__ import annotations
from typing import Optional, List
from uuid import uuid4
from sqlalchemy.orm import Session

from app.domain.models import User, Role
from app.core.security import hash_password

class UserRepo:
    def __init__(self, db: Session):
        self.db = db

    # ---------- GET ----------
    def get(self, user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()

    def list(self, q: Optional[str] = None, limit: int = 100) -> List[User]:
        qry = self.db.query(User)
        if q:
            like = f"%{q}%"
            qry = qry.filter(User.username.like(like))
        return qry.order_by(User.username.asc()).limit(limit).all()

    # ---------- CREATE / UPDATE ----------
    def create(self, username: str, password: str, full_name: str, email: Optional[str], role_name: str, is_active: bool = True) -> User:
        role = self.db.query(Role).filter(Role.name == role_name).first()
        if not role:
            role = Role(id=1 if role_name == "admin" else None, name=role_name)
            self.db.add(role)
            self.db.commit()
            self.db.refresh(role)

        u = User(
            id=str(uuid4()),
            username=username,
            password_hash=hash_password(password),
            full_name=full_name,
            email=email,
            role_id=role.id,
            is_active=is_active,
        )
        self.db.add(u)
        self.db.commit()
        self.db.refresh(u)
        return u

    def set_password(self, user_id: str, new_password: str):
        u = self.get(user_id)
        if not u:
            return
        u.password_hash = hash_password(new_password)
        self.db.commit()

    def set_active(self, user_id: str, active: bool):
        u = self.get(user_id)
        if not u:
            return
        u.is_active = active
        self.db.commit()

    # ---------- BOOTSTRAP ----------
    def bootstrap_roles_and_admin(self):
        """
        Crea roles base (admin, medico, viewer) y un usuario admin si no existe.
        """
        # roles
        roles = [("admin", 1), ("medico", 2), ("viewer", 3)]
        for name, rid in roles:
            r = self.db.query(Role).filter(Role.name == name).first()
            if not r:
                self.db.add(Role(id=rid, name=name))
        self.db.commit()

        # admin
        admin = self.get_by_username("admin")
        if not admin:
            self.create(
                username="admin",
                password="TuPassFuerte123!",
                full_name="Administrador",
                email="admin@example.com",
                role_name="admin",
                is_active=True,
            )