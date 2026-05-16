from dataclasses import dataclass


@dataclass(slots=True)
class PromptRow:
    prompt_id: str
    title: str
    lyrics: str
    style: str
    tags: str
