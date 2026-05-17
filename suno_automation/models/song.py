from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class SongResult:
    prompt_id: str
    title: str
    status: str
    suno_track_id: Optional[str] = None
    download_url: Optional[str] = None
    local_path: Optional[Path] = None
    attempts: int = 0
    error: Optional[str] = None
    created_at: datetime = datetime.utcnow()
