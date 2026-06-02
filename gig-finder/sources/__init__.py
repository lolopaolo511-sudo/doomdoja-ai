"""Source adapters for gig-finder."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Gig:
    id: str
    title: str
    url: str
    description: str
    budget: str
    source: str
    posted_at: str = ""
    tags: list[str] = field(default_factory=list)

    def text_blob(self) -> str:
        return f"{self.title}\n{self.description}\n{' '.join(self.tags)}"
