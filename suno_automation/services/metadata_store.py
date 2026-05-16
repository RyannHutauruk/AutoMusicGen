import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from suno_automation.models.song import SongResult


class MetadataStore:
    @staticmethod
    def save_json(results: Iterable[SongResult], output_dir: Path, filename: str = "results.json") -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = []
        for result in results:
            row = asdict(result)
            if row.get("local_path"):
                row["local_path"] = str(row["local_path"])
            row["created_at"] = result.created_at.isoformat()
            payload.append(row)

        target = output_dir / filename
        with target.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return target
