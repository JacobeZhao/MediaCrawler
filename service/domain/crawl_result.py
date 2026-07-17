from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class CrawlResult:
    notes_count: int = 0
    comments_count: int = 0
    creators_count: int = 0
    request_count: int = 0
    billed_success_count: int = 0
    budget_exhausted: bool = False
    checkpoint: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "notes_count": self.notes_count,
            "comments_count": self.comments_count,
            "creators_count": self.creators_count,
            "request_count": self.request_count,
            "billed_success_count": self.billed_success_count,
            "budget_exhausted": self.budget_exhausted,
            "checkpoint": dict(self.checkpoint),
        }
