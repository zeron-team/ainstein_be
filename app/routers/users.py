# app/routers/users.py
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, role_required
from app.domain.models import User
from app.domain.schemas import UserCreate, UserUpdate, Msg
from app.repositories.user_repo import UserRepo

router = APIRouter(tags=["Users"])


def serialize_user(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "email": u.email,
        "role": u.role.name if u.role else None,
        "is_active": u.is_active,
    }


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _current=Depends(role_required("admin")),
) -> List[dict]:
    rows = UserRepo(db).list()
    return [serialize_user(u) for u in rows]


@router.get("/users/{user_id}")
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    _current=Depends(role_required("admin")),
) -> dict:
    repo = UserRepo(db)
    u = repo.get(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return serialize_user(u)


@router.post("/users")
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _current=Depends(role_required("admin")),
) -> dict:
    repo = UserRepo(db)
    if repo.get_by_username(payload.username):
        raise HTTPException(status_code=400, detail="Usuario ya existe")

    user = repo.create(
        username=payload.username,
        password=payload.password,
        full_name=payload.full_name,
        email=payload.email,
        role_name=payload.role,   # "admin" | "medico" | "viewer"
        is_active=True,
    )
    return serialize_user(user)


@router.put("/users/{user_id}")
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _current=Depends(role_required("admin")),
) -> dict:
    repo = UserRepo(db)
    u = repo.get(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    updated = repo.update(
        u,
        full_name=payload.full_name,
        email=payload.email,
        role_name=payload.role,
        is_active=payload.is_active,
    )
    return serialize_user(updated)


@router.delete("/users/{user_id}", response_model=Msg)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    _current=Depends(role_required("admin")),
) -> Msg:
    repo = UserRepo(db)
    ok = repo.delete(user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return Msg(message="Usuario eliminado")