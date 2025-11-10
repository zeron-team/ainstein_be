from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid
from app.core.deps import get_db, role_required
from app.core.security import hash_password
from app.domain.models import User
from app.domain.schemas import UserCreate
from app.repositories.user_repo import UserRepo

router = APIRouter(tags=["Users"])

@router.get("/users")
def list_users(db: Session = Depends(get_db), user=Depends(role_required('admin'))):
    rows = UserRepo(db).list()
    out = []
    for u in rows:
        out.append({"id": u.id, "username": u.username, "full_name": u.full_name, "email": u.email, "role": u.role.name, "is_active": u.is_active})
    return out

@router.post("/users")
def create_user(payload: UserCreate, db: Session = Depends(get_db), user=Depends(role_required('admin'))):
    repo = UserRepo(db)
    if repo.get_by_username(payload.username):
        raise HTTPException(status_code=400, detail="Usuario ya existe")
    m = User(
        id=str(uuid.uuid4()), username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name, email=payload.email,
        role_id=payload.role_id, is_active=True
    )
    return repo.create(m)
