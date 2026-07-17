from __future__ import annotations

import re
from typing import Any, Mapping, Optional, Sequence

from ...domain import CanonicalComment, CanonicalCreator, CanonicalNote


_NOTE_LIST_KEYS = ("items", "notes", "noteList", "note_list", "list", "records")
_COMMENT_LIST_KEYS = (
    "comments",
    "subComments",
    "sub_comments",
    "commentList",
    "comment_list",
    "items",
    "list",
    "records",
)
_ID_PATTERN = re.compile(r"(?:explore|discovery/item)/([0-9a-zA-Z]+)")
_CREATOR_PATTERN = re.compile(r"user/profile/([0-9a-zA-Z]+)")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _pick(item: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = item.get(key)
        if _present(value):
            return value
    return default


def _text(value: Any) -> Optional[str]:
    if not _present(value):
        return None
    return str(value).strip()


def _integer(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _boolean(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _strings(value: Any, *url_keys: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    result: list[str] = []
    for entry in value:
        if isinstance(entry, Mapping):
            candidate = _pick(entry, *url_keys)
            if not candidate:
                candidates = _pick(entry, "urlList", "url_list", "infoList", default=[])
                if isinstance(candidates, Sequence) and not isinstance(candidates, (str, bytes)):
                    candidate = next((_text(item) for item in candidates if _text(item)), None)
        else:
            candidate = entry
        text = _text(candidate)
        if text and text not in result:
            result.append(text)
    return result


def _unwrap(item: Any, *keys: str) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    outer = _mapping(item)
    for key in keys:
        nested = outer.get(key)
        if isinstance(nested, Mapping):
            return outer, nested
    return outer, outer


class JustOneApiNormalizer:
    @staticmethod
    def list_items(data: Any, *, comments: bool = False) -> list[Mapping[str, Any]]:
        if isinstance(data, Sequence) and not isinstance(data, (str, bytes)):
            return [item for item in data if isinstance(item, Mapping)]
        container = _mapping(data)
        keys = _COMMENT_LIST_KEYS if comments else _NOTE_LIST_KEYS
        for key in keys:
            value = container.get(key)
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                return [item for item in value if isinstance(item, Mapping)]
        nested = container.get("data")
        if nested is not data and isinstance(nested, (Mapping, list, tuple)):
            return JustOneApiNormalizer.list_items(nested, comments=comments)
        return []

    @staticmethod
    def note(item: Any, *, source_keyword: str = "") -> Optional[CanonicalNote]:
        outer, note = _unwrap(
            item,
            "noteCard",
            "note_card",
            "noteInfo",
            "note_info",
            "note",
        )
        note_id = _text(
            _pick(note, "noteId", "note_id", "id")
            or _pick(outer, "noteId", "note_id", "id")
        )
        if not note_id:
            return None

        user = _mapping(_pick(note, "user", "userInfo", "user_info", "author", default={}))
        metrics = _mapping(
            _pick(
                note,
                "interactInfo",
                "interact_info",
                "statistics",
                "metrics",
                default={},
            )
        )
        image_urls = _strings(
            _pick(note, "imageList", "image_list", "images", default=[]),
            "urlDefault",
            "url_default",
            "url",
            "original",
        )
        cover = _mapping(_pick(note, "cover", default={}))
        cover_url = _text(_pick(cover, "urlDefault", "url_default", "url"))
        if cover_url and cover_url not in image_urls:
            image_urls.insert(0, cover_url)

        tags_value = _pick(note, "tagList", "tag_list", "tags", default=[])
        tags: list[str] = []
        if isinstance(tags_value, Sequence) and not isinstance(tags_value, (str, bytes)):
            for tag in tags_value:
                value = _pick(tag, "name", "title") if isinstance(tag, Mapping) else tag
                text = _text(value)
                if text and text not in tags:
                    tags.append(text)

        xsec_token = _text(
            _pick(note, "xsecToken", "xsec_token")
            or _pick(outer, "xsecToken", "xsec_token")
        ) or ""
        note_url = _text(_pick(note, "noteUrl", "note_url", "url"))
        if not note_url:
            note_url = f"https://www.xiaohongshu.com/explore/{note_id}"
        video_url = _text(_pick(note, "videoUrl", "video_url"))
        if not video_url:
            video = _mapping(_pick(note, "video", default={}))
            video_url = _text(_pick(video, "url", "masterUrl", "master_url"))
        note_type = _text(_pick(note, "type", "noteType", "note_type"))
        if note_type:
            note_type = "video" if "video" in note_type.lower() else "normal"

        return CanonicalNote(
            note_id=note_id,
            type=note_type,
            title=_text(_pick(note, "title", "displayTitle", "display_title")),
            desc=_text(_pick(note, "desc", "description", "content")),
            video_url=video_url,
            time=_integer(_pick(note, "time", "createTime", "create_time", "publishTime")),
            last_update_time=_integer(
                _pick(note, "lastUpdateTime", "last_update_time", "updateTime")
            ),
            user_id=_text(_pick(user, "userId", "user_id", "id", "redId")),
            nickname=_text(_pick(user, "nickname", "nickName", "name")),
            avatar=_text(_pick(user, "avatar", "image", "avatarUrl", "avatar_url")),
            ip_location=_text(_pick(note, "ipLocation", "ip_location")),
            liked_count=_pick(
                metrics,
                "likedCount",
                "liked_count",
                "likes",
                default=_pick(note, "likedCount", "liked_count"),
            ),
            collected_count=_pick(
                metrics,
                "collectedCount",
                "collected_count",
                "collects",
                default=_pick(note, "collectedCount", "collected_count"),
            ),
            comment_count=_pick(
                metrics,
                "commentCount",
                "comment_count",
                "comments",
                default=_pick(note, "commentCount", "comment_count"),
            ),
            share_count=_pick(
                metrics,
                "shareCount",
                "share_count",
                "shares",
                default=_pick(note, "shareCount", "share_count"),
            ),
            image_list=image_urls,
            tag_list=tags,
            note_url=note_url,
            source_keyword=source_keyword,
            xsec_token=xsec_token,
        )

    @staticmethod
    def comment(item: Any, *, note_id: str) -> Optional[CanonicalComment]:
        _, comment = _unwrap(item, "comment", "commentInfo", "comment_info")
        comment_id = _text(_pick(comment, "commentId", "comment_id", "id"))
        resolved_note_id = _text(_pick(comment, "noteId", "note_id")) or note_id
        if not comment_id or not resolved_note_id:
            return None
        user = _mapping(_pick(comment, "userInfo", "user_info", "user", default={}))
        target = _mapping(_pick(comment, "targetComment", "target_comment", default={}))
        pictures = _strings(
            _pick(comment, "pictures", "imageList", "image_list", default=[]),
            "urlDefault",
            "url_default",
            "url",
        )
        sub_count = None
        for key in ("subCommentCount", "sub_comment_count", "replyCount", "reply_count"):
            if key in comment:
                sub_count = _integer(comment.get(key))
                break
        return CanonicalComment(
            comment_id=comment_id,
            note_id=resolved_note_id,
            create_time=_integer(_pick(comment, "createTime", "create_time", "time")),
            ip_location=_text(_pick(comment, "ipLocation", "ip_location")),
            content=_text(_pick(comment, "content", "text")),
            user_id=_text(_pick(user, "userId", "user_id", "id")),
            nickname=_text(_pick(user, "nickname", "nickName", "name")),
            avatar=_text(_pick(user, "image", "avatar", "avatarUrl", "avatar_url")),
            sub_comment_count=sub_count,
            pictures=pictures,
            parent_comment_id=_text(
                _pick(target, "id", "commentId", "comment_id")
                or _pick(comment, "parentCommentId", "parent_comment_id")
            )
            or "",
            like_count=_pick(comment, "likeCount", "like_count", "likes"),
        )

    @staticmethod
    def creator(item: Any, *, fallback_user_id: str = "") -> Optional[CanonicalCreator]:
        outer, creator = _unwrap(item, "basicInfo", "basic_info", "user", "userInfo")
        user_id = _text(
            _pick(creator, "userId", "user_id", "id", "redId") or fallback_user_id
        )
        if not user_id:
            return None
        interactions = _pick(outer, "interactions", "interactionInfo", default=[])
        metrics: dict[str, Any] = {}
        if isinstance(interactions, Mapping):
            metrics.update(interactions)
        elif isinstance(interactions, Sequence) and not isinstance(interactions, (str, bytes)):
            for interaction in interactions:
                if not isinstance(interaction, Mapping):
                    continue
                metric_type = _text(_pick(interaction, "type", "name"))
                if metric_type:
                    metrics[metric_type.lower()] = _pick(interaction, "count", "value")
        tags_value = _pick(outer, "tags", "tagList", "tag_list", default=[])
        tags: list[str] = []
        if isinstance(tags_value, Sequence) and not isinstance(tags_value, (str, bytes)):
            for tag in tags_value:
                value = _pick(tag, "name", "title") if isinstance(tag, Mapping) else tag
                text = _text(value)
                if text:
                    tags.append(text)
        return CanonicalCreator(
            user_id=user_id,
            nickname=_text(_pick(creator, "nickname", "nickName", "name")),
            avatar=_text(_pick(creator, "avatar", "images", "image", "avatarUrl")),
            ip_location=_text(_pick(creator, "ipLocation", "ip_location")),
            desc=_text(_pick(creator, "desc", "description", "bio")),
            gender=_text(_pick(creator, "gender")),
            follows=_pick(
                metrics,
                "follows",
                "following",
                default=_pick(outer, "follows", "followingCount"),
            ),
            fans=_pick(
                metrics,
                "fans",
                "followers",
                default=_pick(outer, "fans", "fansCount", "followersCount"),
            ),
            interaction=_pick(
                metrics,
                "interaction",
                "interactions",
                default=_pick(outer, "interaction", "interactionCount"),
            ),
            tag_list=tags,
        )

    @staticmethod
    def pagination(data: Any) -> dict[str, Any]:
        container = _mapping(data)
        api_info = _mapping(_pick(container, "api_info", "apiInfo", default={}))
        return {
            "has_more": _boolean(
                _pick(container, "hasMore", "has_more", "hasNext", "has_next", default=False)
            ),
            "cursor": _text(
                _pick(container, "cursor", "nextCursor", "next_cursor", "lastCursor")
            ),
            "search_id": _text(
                _pick(
                    container,
                    "searchId",
                    "search_id",
                    default=_pick(api_info, "searchId", "search_id"),
                )
            ),
            "session_id": _text(
                _pick(
                    container,
                    "sessionId",
                    "session_id",
                    default=_pick(api_info, "sessionId", "session_id"),
                )
            ),
        }

    @staticmethod
    def note_id(value: str) -> Optional[str]:
        text = str(value or "").strip()
        if not text:
            return None
        match = _ID_PATTERN.search(text)
        if match:
            return match.group(1)
        if "/" not in text and "?" not in text and len(text) <= 128:
            return text
        return None

    @staticmethod
    def creator_id(value: str) -> Optional[str]:
        text = str(value or "").strip()
        if not text:
            return None
        match = _CREATOR_PATTERN.search(text)
        if match:
            return match.group(1)
        if "/" not in text and "?" not in text and len(text) <= 128:
            return text
        return None

    @staticmethod
    def resolved_url(data: Any) -> Optional[str]:
        if isinstance(data, str):
            return _text(data)
        container = _mapping(data)
        return _text(
            _pick(
                container,
                "url",
                "link",
                "resolvedUrl",
                "resolved_url",
                "targetUrl",
                "finalUrl",
                "jumpUrl",
            )
        )
