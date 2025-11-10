from app.domain.models import User, Role
from sqlalchemy.orm import Session

class UserRepo:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: str):
        return self.db.get(User, user_id)

    def get_by_username(self, username: str):
        return self.db.query(User).filter(User.username == username).first()

    def create(self, user: User):
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def list(self, q: str | None = None, limit: int = 100):
        query = self.db.query(User).join(Role)
        if q:
            query = query.filter(User.username.like(f"%{q}%"))
        return query.limit(limit).all()
