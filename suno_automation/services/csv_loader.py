import csv
from pathlib import Path
from typing import List

from suno_automation.models.prompt import PromptRow


class CSVLoader:
    @staticmethod
    def load_prompts(csv_path: Path) -> List[PromptRow]:
        rows: List[PromptRow] = []
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(
                    PromptRow(
                        prompt_id=row.get("prompt_id", "").strip(),
                        title=row.get("title", "Untitled").strip(),
                        lyrics=row.get("lyrics", "").strip(),
                        style=row.get("style", "").strip(),
                        tags=row.get("tags", "").strip(),
                    )
                )
        return rows
