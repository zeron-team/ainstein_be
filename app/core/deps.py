from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import decode_token
from app.repositories.user_repo import UserRepo
from app.db.session import SessionLocal
# FERRO: Import Redis
from app.core.redis import get_redis as _get_redis

bearer = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FERRO: Redis Dependency
async def get_redis():
    return await _get_redis()

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db=Depends(get_db)):
    token = creds.credentials
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    user = UserRepo(db).get(payload.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario inactivo")
    return {"id": user.id, "role": payload.get("role"), "username": user.username}

def role_required(*roles):
    def checker(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Permiso denegado")
        return user
    return checker
