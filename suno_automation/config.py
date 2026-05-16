from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


class Settings(BaseModel):
    base_url: str = Field(default="https://suno.com")
    login_url: str = Field(default="https://suno.com/sign-in")
    create_url: str = Field(default="https://suno.com/create")

    login_method: str = Field(default_factory=lambda: os.getenv("SUNO_LOGIN_METHOD", "google").lower())
    email: str = Field(default_factory=lambda: os.getenv("SUNO_EMAIL", ""))
    password: str = Field(default_factory=lambda: os.getenv("SUNO_PASSWORD", ""))
    google_email: str = Field(default_factory=lambda: os.getenv("SUNO_GOOGLE_EMAIL", os.getenv("SUNO_EMAIL", "")))
    google_password: str = Field(default_factory=lambda: os.getenv("SUNO_GOOGLE_PASSWORD", os.getenv("SUNO_PASSWORD", "")))

    csv_path: Path = Field(default=PROJECT_ROOT / "suno_automation" / "data" / "prompts.csv")
    output_audio_dir: Path = Field(default=PROJECT_ROOT / "suno_automation" / "output" / "audio")
    output_metadata_dir: Path = Field(default=PROJECT_ROOT / "suno_automation" / "output" / "metadata")
    user_data_dir: Path = Field(default=PROJECT_ROOT / "suno_profile")

    headless: bool = Field(default=os.getenv("HEADLESS", "false").lower() == "true")
    max_retries: int = Field(default=int(os.getenv("MAX_RETRIES", "3")))
    concurrency: int = Field(default=int(os.getenv("CONCURRENCY", "2")))
    poll_interval_seconds: int = Field(default=int(os.getenv("POLL_INTERVAL_SECONDS", "8")))
    timeout_ms: int = Field(default=int(os.getenv("TIMEOUT_MS", "90000")))
    manual_login_timeout_seconds: int = Field(default=int(os.getenv("MANUAL_LOGIN_TIMEOUT_SECONDS", "180")))


settings = Settings()
