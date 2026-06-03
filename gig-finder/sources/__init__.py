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
    open_status: str = "nieznany"   # "otwarte" | "świeże" | "brak daty" | "nieznany"
    tags: list[str] = field(default_factory=list)

    def text_blob(self) -> str:
        return f"{self.title}\n{self.description}\n{' '.join(self.tags)}"

    def age_days(self) -> Optional[int]:
        ref = self.posted_dt
        if ref is None and self.posted_at:
            try:
                ref = datetime.strptime(self.posted_at[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        if ref is None:
            return None
        now = datetime.now(timezone.utc)
        dt = ref if ref.tzinfo else ref.replace(tzinfo=timezone.utc)
        return max(0, (now - dt).days)

    def age_str(self) -> str:
        days = self.age_days()
        if days is None:
            return "brak daty"
        if days == 0:
            return "dziś"
        if days == 1:
            return "wczoraj"
        return f"{days} dni temu"
