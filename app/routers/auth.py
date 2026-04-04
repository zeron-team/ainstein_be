# backend/app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from app.core.deps import get_db
from app.repositories.user_repo import UserRepo
from app.core.security import verify_password, create_access_token
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/auth", tags=["Auth"])

# Limiter instance for this router (shares config with app-level limiter)
limiter = Limiter(key_func=get_remote_address)


class LoginReq(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, req: LoginReq, db=Depends(get_db)):
    user = UserRepo(db).get_by_username(req.username)
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = create_access_token(user.id, user.role.name)
    return {
        "access_token": token,
        "role": user.role.name,
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
        },
    }
