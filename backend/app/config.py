from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PHYSIOFLOW_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./physioflow-dev.db"
    session_hours: int = 12
    # Must be true as soon as the app is served via HTTPS (production).
    cookie_secure: bool = False
    # Geschützter lokaler Speicher für Bilder, PDFs und Zeichnungen (liegt NICHT im Web-Verzeichnis).
    data_dir: Path = Path("./data")
    max_upload_mb: int = 25
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    # Lokale Assistenzdienste (alle optional; nur Adressen im eigenen Netz sind erlaubt)
    whisper_url: str | None = None
    ocr_enabled: bool = True
    llm_url: str | None = None
    llm_model: str = "llama3.1"
    # Directory containing the built frontend (index.html); served by the backend if present.
    frontend_dist: Path | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
