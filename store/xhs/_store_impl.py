import json
from typing import Any, Dict, List, Optional

from base.base_crawler import AbstractStore
from database.db_session import get_session
from database.models import XhsContentSource, XhsCreator, XhsNote, XhsNoteComment
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from tools.time_util import get_current_timestamp
from var import source_keyword_var


_EMPTY_TEXT_VALUES = {"", "none", "null", '""', "[]", "{}"}


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in _EMPTY_TEXT_VALUES
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _clean_business_key(value: Any) -> str:
    return str(value or "").strip()


def _as_text(value: Any) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _positive_timestamp(value: Any) -> Optional[int]:
    if not _has_value(value):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _put_if_present(
    target: Dict[str, Any],
    source: Dict[str, Any],
    field: str,
    transform=None,
) -> None:
    value = source.get(field)
    if not _has_value(value):
        return
    target[field] = transform(value) if transform else value


def _normalize_task_id(task_id: Optional[int]) -> int:
    try:
        value = int(task_id or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, value)


class XhsSqliteStoreImplement(AbstractStore):
    async def store_content(
        self,
        content_item: Dict,
        *,
        provider: str = "local",
        task_id: Optional[int] = None,
        source_keyword: Optional[str] = None,
    ):
        note_id = _clean_business_key(content_item.get("note_id"))
        if not note_id:
            return
        now = int(get_current_timestamp())
        values = self._content_values(content_item, note_id, now)
        async with get_session() as session:
            statement = sqlite_insert(XhsNote).values(**values)
            update_values = {
                field: getattr(statement.excluded, field)
                for field in values
                if field not in {"note_id", "add_ts", "source_keyword"}
            }
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[XhsNote.note_id],
                    set_=update_values,
                )
            )
            await self._record_source(
                session,
                "note",
                note_id,
                provider,
                task_id,
                self._source_keyword(content_item, source_keyword),
                now,
            )

    async def add_content(self, session: AsyncSession, content_item: Dict):
        note_id = _clean_business_key(content_item.get("note_id"))
        if not note_id:
            return
        session.add(XhsNote(**self._content_values(content_item, note_id, int(get_current_timestamp()))))

    async def update_content(self, session: AsyncSession, content_item: Dict):
        note_id = _clean_business_key(content_item.get("note_id"))
        if not note_id:
            return
        values = self._content_values(content_item, note_id, int(get_current_timestamp()))
        update_values = {
            field: value
            for field, value in values.items()
            if field not in {"note_id", "add_ts", "source_keyword"}
        }
        await session.execute(
            update(XhsNote).where(XhsNote.note_id == note_id).values(**update_values)
        )

    async def content_is_exist(self, session: AsyncSession, note_id: str) -> bool:
        result = await session.execute(select(XhsNote.id).where(XhsNote.note_id == note_id))
        return result.first() is not None

    async def store_comment(
        self,
        comment_item: Dict,
        *,
        provider: str = "local",
        task_id: Optional[int] = None,
        source_keyword: Optional[str] = None,
    ):
        if not comment_item:
            return
        comment_id = _clean_business_key(comment_item.get("comment_id"))
        if not comment_id:
            return
        now = int(get_current_timestamp())
        values = self._comment_values(comment_item, comment_id, now)
        async with get_session() as session:
            statement = sqlite_insert(XhsNoteComment).values(**values)
            update_values = {
                field: getattr(statement.excluded, field)
                for field in values
                if field not in {"comment_id", "add_ts", "note_id"}
            }
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[XhsNoteComment.comment_id],
                    set_=update_values,
                )
            )
            await self._record_source(
                session,
                "comment",
                comment_id,
                provider,
                task_id,
                self._source_keyword(comment_item, source_keyword),
                now,
            )

    async def add_comment(self, session: AsyncSession, comment_item: Dict):
        comment_id = _clean_business_key(comment_item.get("comment_id"))
        if not comment_id:
            return
        session.add(
            XhsNoteComment(
                **self._comment_values(comment_item, comment_id, int(get_current_timestamp()))
            )
        )

    async def update_comment(self, session: AsyncSession, comment_item: Dict):
        comment_id = _clean_business_key(comment_item.get("comment_id"))
        if not comment_id:
            return
        values = self._comment_values(comment_item, comment_id, int(get_current_timestamp()))
        update_values = {
            field: value
            for field, value in values.items()
            if field not in {"comment_id", "add_ts", "note_id"}
        }
        await session.execute(
            update(XhsNoteComment)
            .where(XhsNoteComment.comment_id == comment_id)
            .values(**update_values)
        )

    async def comment_is_exist(self, session: AsyncSession, comment_id: str) -> bool:
        result = await session.execute(
            select(XhsNoteComment.id).where(XhsNoteComment.comment_id == comment_id)
        )
        return result.first() is not None

    async def store_creator(
        self,
        creator_item: Dict,
        *,
        provider: str = "local",
        task_id: Optional[int] = None,
        source_keyword: Optional[str] = None,
    ):
        user_id = _clean_business_key(creator_item.get("user_id"))
        if not user_id:
            return
        now = int(get_current_timestamp())
        values = self._creator_values(creator_item, user_id, now)
        async with get_session() as session:
            statement = sqlite_insert(XhsCreator).values(**values)
            update_values = {
                field: getattr(statement.excluded, field)
                for field in values
                if field not in {"user_id", "add_ts"}
            }
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[XhsCreator.user_id],
                    set_=update_values,
                )
            )
            await self._record_source(
                session,
                "creator",
                user_id,
                provider,
                task_id,
                self._source_keyword(creator_item, source_keyword),
                now,
            )

    async def add_creator(self, session: AsyncSession, creator_item: Dict):
        user_id = _clean_business_key(creator_item.get("user_id"))
        if not user_id:
            return
        session.add(
            XhsCreator(
                **self._creator_values(creator_item, user_id, int(get_current_timestamp()))
            )
        )

    async def update_creator(self, session: AsyncSession, creator_item: Dict):
        user_id = _clean_business_key(creator_item.get("user_id"))
        if not user_id:
            return
        values = self._creator_values(creator_item, user_id, int(get_current_timestamp()))
        update_values = {
            field: value
            for field, value in values.items()
            if field not in {"user_id", "add_ts"}
        }
        await session.execute(
            update(XhsCreator).where(XhsCreator.user_id == user_id).values(**update_values)
        )

    async def creator_is_exist(self, session: AsyncSession, user_id: str) -> bool:
        result = await session.execute(select(XhsCreator.id).where(XhsCreator.user_id == user_id))
        return result.first() is not None

    async def get_all_content(self) -> List[Dict]:
        async with get_session() as session:
            result = await session.execute(select(XhsNote))
            return [item.__dict__ for item in result.scalars().all()]

    async def get_all_comments(self) -> List[Dict]:
        async with get_session() as session:
            result = await session.execute(select(XhsNoteComment))
            return [item.__dict__ for item in result.scalars().all()]

    @staticmethod
    def _content_values(content_item: Dict, note_id: str, now: int) -> Dict[str, Any]:
        values: Dict[str, Any] = {
            "note_id": note_id,
            "add_ts": now,
            "last_modify_ts": now,
        }
        for field in (
            "user_id",
            "nickname",
            "avatar",
            "ip_location",
            "type",
            "title",
            "desc",
            "video_url",
            "note_url",
            "xsec_token",
        ):
            _put_if_present(values, content_item, field, _as_text)
        for field in ("liked_count", "collected_count", "comment_count", "share_count"):
            _put_if_present(values, content_item, field, _as_text)
        for field in ("image_list", "tag_list"):
            _put_if_present(values, content_item, field, _as_json)
        for field in ("time", "last_update_time"):
            parsed = _positive_timestamp(content_item.get(field))
            if parsed is not None:
                values[field] = parsed
        if _has_value(content_item.get("source_keyword")):
            values["source_keyword"] = _as_text(content_item["source_keyword"])
        return values

    @staticmethod
    def _comment_values(comment_item: Dict, comment_id: str, now: int) -> Dict[str, Any]:
        values: Dict[str, Any] = {
            "comment_id": comment_id,
            "add_ts": now,
            "last_modify_ts": now,
        }
        for field in (
            "user_id",
            "nickname",
            "avatar",
            "ip_location",
            "note_id",
            "content",
            "parent_comment_id",
            "like_count",
        ):
            _put_if_present(values, comment_item, field, _as_text)
        _put_if_present(values, comment_item, "pictures", _as_json)
        if "sub_comment_count" in comment_item and _has_value(comment_item.get("sub_comment_count")):
            try:
                values["sub_comment_count"] = int(comment_item["sub_comment_count"])
            except (TypeError, ValueError):
                pass
        create_time = _positive_timestamp(comment_item.get("create_time"))
        if create_time is not None:
            values["create_time"] = create_time
        return values

    @staticmethod
    def _creator_values(creator_item: Dict, user_id: str, now: int) -> Dict[str, Any]:
        values: Dict[str, Any] = {
            "user_id": user_id,
            "add_ts": now,
            "last_modify_ts": now,
        }
        for field in (
            "nickname",
            "avatar",
            "ip_location",
            "desc",
            "gender",
            "follows",
            "fans",
            "interaction",
        ):
            _put_if_present(values, creator_item, field, _as_text)
        _put_if_present(values, creator_item, "tag_list", _as_json)
        return values

    @staticmethod
    def _source_keyword(item: Dict, explicit_keyword: Optional[str]) -> str:
        for value in (explicit_keyword, item.get("source_keyword"), source_keyword_var.get()):
            if _has_value(value):
                return str(value).strip()
        return ""

    @staticmethod
    async def _record_source(
        session: AsyncSession,
        entity_type: str,
        entity_id: str,
        provider: str,
        task_id: Optional[int],
        source_keyword: str,
        now: int,
    ) -> None:
        statement = sqlite_insert(XhsContentSource).values(
            entity_type=entity_type,
            entity_id=entity_id,
            provider=str(provider or "local").strip().lower() or "local",
            task_id=_normalize_task_id(task_id),
            source_keyword=source_keyword,
            first_seen_ts=now,
            last_seen_ts=now,
        )
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[
                    XhsContentSource.entity_type,
                    XhsContentSource.entity_id,
                    XhsContentSource.provider,
                    XhsContentSource.task_id,
                    XhsContentSource.source_keyword,
                ],
                set_={"last_seen_ts": statement.excluded.last_seen_ts},
            )
        )
