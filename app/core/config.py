from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    SQL_URL: str
    MONGO_URL: str
    JWT_SECRET: str
    JWT_EXPIRE_MINUTES: int = 60
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-1.5-pro"
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]
    HCE_UPLOAD_DIR: str = os.getenv("HCE_UPLOAD_DIR", "/tmp/hce_uploads")

    class Config:
        env_file = ".env"

settings = Settings()
