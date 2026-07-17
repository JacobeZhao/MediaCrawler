from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal


NoteType = Literal["ALL", "NORMAL_NOTE", "VIDEO_NOTE"]
TimeFilter = Literal["ALL", "ONE_DAY", "ONE_WEEK", "HALF_YEAR"]


@dataclass(frozen=True)
class JustOneApiTaskOptionDefaults:
    include_details: bool = True
    include_comments: bool = False
    include_replies: bool = False
    max_pages: int = 3
    max_requests: int = 20
    note_type: NoteType = "ALL"
    time_filter: TimeFilter = "ALL"


TASK_OPTION_DEFAULTS: Final = JustOneApiTaskOptionDefaults()
PAGE_LIMIT_MIN: Final = 1
PAGE_LIMIT_MAX: Final = 100
REQUEST_BUDGET_MIN: Final = 1
REQUEST_BUDGET_MAX: Final = 1000
TRANSPORT_SORT_TYPE_DEFAULT: Final = "general"
