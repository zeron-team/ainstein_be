from __future__ import annotations

from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices
import json


def _parse_cors(value: Union[str, List[str], None]) -> List[str]:
    default = ["http://localhost:5173", "http://127.0.0.1:5173"]
    if value is None:
        return default
    if isinstance(value, list):
        return value or default
    v = value.strip()
    if not v:
        return default
    if v.startswith("["):
        try:
            arr = json.loads(v)
            return list(arr) if isinstance(arr, list) else default
        except Exception:
            return default
    return [x.strip() for x in v.split(",") if x.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DBs
    SQL_URL: str
    MONGO_URL: str
    MONGO_DB_NAME: str | None = None  # opcional (si no viene, se infiere del URL)

    # Auth
    JWT_SECRET: str
    JWT_EXPIRE_MINUTES: int = 60

    # Gemini / Google AI
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_API_HOST: str = "https://generativelanguage.googleapis.com"
    GEMINI_API_VERSION: str = "v1beta"

    # Uploads
    HCE_UPLOAD_DIR: str = Field(
        default="/tmp/hce_uploads",
        validation_alias=AliasChoices("HCE_UPLOAD_DIR", "hce_upload_dir", "UPLOAD_DIR"),
    )
    HCE_SUBDIR: str = Field(default="hce", validation_alias=AliasChoices("HCE_SUBDIR", "hce_subdir"))

    # CORS
    CORS_ORIGINS: Union[str, List[str], None] = None
    CORS_ALLOW_ORIGIN_REGEX: str = r"https?://(localhost|127\.0\.0\.1)(:\d{2,5})?$"

    # Misc
    ENV: str = "dev"
    EPC_FALLBACK_ANY_HCE: bool = True  # habilita estrategia ANY en generate()

    def model_post_init(self, *_):
        self.CORS_ORIGINS = _parse_cors(self.CORS_ORIGINS)


settings = Settings()