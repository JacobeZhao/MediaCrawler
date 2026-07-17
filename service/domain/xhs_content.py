from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


def _without_none(value: Dict[str, Any]) -> Dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


@dataclass(frozen=True)
class CanonicalNote:
    note_id: str
    type: Optional[str] = None
    title: Optional[str] = None
    desc: Optional[str] = None
    video_url: Optional[str] = None
    time: Optional[int] = None
    last_update_time: Optional[int] = None
    user_id: Optional[str] = None
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    ip_location: Optional[str] = None
    liked_count: Any = None
    collected_count: Any = None
    comment_count: Any = None
    share_count: Any = None
    image_list: List[str] = field(default_factory=list)
    tag_list: List[str] = field(default_factory=list)
    note_url: Optional[str] = None
    source_keyword: str = ""
    xsec_token: str = ""

    def to_store_dict(self) -> Dict[str, Any]:
        return _without_none(asdict(self))


@dataclass(frozen=True)
class CanonicalComment:
    comment_id: str
    note_id: str
    create_time: Optional[int] = None
    ip_location: Optional[str] = None
    content: Optional[str] = None
    user_id: Optional[str] = None
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    sub_comment_count: Optional[int] = None
    pictures: List[str] = field(default_factory=list)
    parent_comment_id: str = ""
    like_count: Any = None

    def to_store_dict(self) -> Dict[str, Any]:
        return _without_none(asdict(self))


@dataclass(frozen=True)
class CanonicalCreator:
    user_id: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    ip_location: Optional[str] = None
    desc: Optional[str] = None
    gender: Optional[str] = None
    follows: Any = None
    fans: Any = None
    interaction: Any = None
    tag_list: List[str] = field(default_factory=list)

    def to_store_dict(self) -> Dict[str, Any]:
        return _without_none(asdict(self))
