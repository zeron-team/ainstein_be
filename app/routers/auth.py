from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.deps import get_db
from app.repositories.user_repo import UserRepo
from app.core.security import verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Auth"])

class LoginReq(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(req: LoginReq, db=Depends(get_db)):
    user = UserRepo(db).get_by_username(req.username)
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = create_access_token(user.id, user.role.name)
    return {"access_token": token, "role": user.role.name, "user": {"id": user.id, "username": user.username, "full_name": user.full_name}}
