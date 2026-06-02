"""Source adapters for gig-finder."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Gig:
    id: str
    title: str
    url: str
    description: str
    budget: str
    source: str
    posted_at: str = ""
    posted_dt: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)

    def text_blob(self) -> str:
        return f"{self.title}\n{self.description}\n{' '.join(self.tags)}"

    def age_days(self) -> Optional[int]:
        if self.posted_dt is None:
            return None
        now = datetime.now(timezone.utc)
        dt = self.posted_dt if self.posted_dt.tzinfo else self.posted_dt.replace(tzinfo=timezone.utc)
        return max(0, (now - dt).days)

    def age_str(self) -> str:
        days = self.age_days()
        if days is None:
            return "—"
        if days == 0:
            return "dziś"
        if days == 1:
            return "1 dzień temu"
        return f"{days} dni temu"
