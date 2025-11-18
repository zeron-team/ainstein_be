# backend/app/repositories/branding_repo.py
from sqlalchemy.orm import Session
from app.domain.models import Branding

class BrandingRepo:
    def __init__(self, db: Session):
        self.db = db
    def get_active(self) -> Branding | None:
        return self.db.get(Branding, 1)
    def update(self, data: dict) -> Branding:
        b = self.db.get(Branding, 1)
        if not b:
            b = Branding(id=1)
            self.db.add(b)
        for k, v in data.items():
            setattr(b, k, v)
        self.db.commit()
        self.db.refresh(b)
        return b
