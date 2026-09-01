from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Dict, Mapping, Optional, Protocol

from config.settings import settings
from store.xhs import XhsStoreFactory

from .. import service_db as db
from ..domain import CanonicalNote, CrawlResult
from ..providers.justoneapi.client import JustOneApiClient
from ..providers.justoneapi.errors import (
    JustOneApiBalanceError,
    JustOneApiCredentialError,
    JustOneApiDailyQuotaError,
    JustOneApiError,
    JustOneApiHttpError,
    JustOneApiProtocolError,
    JustOneApiRateLimitError,
    JustOneApiTokenLimitError,
    JustOneApiTransportError,
    JustOneApiUpstreamError,
    error_from_envelope,
)
from ..providers.justoneapi.models import ApiEnvelope, RequestRecord
from ..providers.justoneapi.normalizer import JustOneApiNormalizer
from ..providers.justoneapi.options import (
    PAGE_LIMIT_MAX,
    PAGE_LIMIT_MIN,
    REQUEST_BUDGET_MAX,
    REQUEST_BUDGET_MIN,
    TASK_OPTION_DEFAULTS,
    TRANSPORT_SORT_TYPE_DEFAULT,
)
from .base import (
    ExecutionContext,
    ExecutorLeaseLost,
    ExecutorPaused,
    ProviderReadiness,
    TaskExecutor,
)


class _Store(Protocol):
    async def store_content(self, content_item: Dict, **kwargs): ...

    async def store_comment(self, comment_item: Dict, **kwargs): ...

    async def store_creator(self, creator_item: Dict, **kwargs): ...


class _RequestBudgetExhausted(Exception):
    pass


class _RunState:
    def __init__(
        self,
        context: ExecutionContext,
        max_requests: int,
        result: CrawlResult,
        checkpoint: Dict[str, Any],
    ):
        self.context = context
        self.max_requests = max(1, max_requests)
        self.result = result
        self.checkpoint = checkpoint
        self._inflight_request_id: Optional[int] = None

    async def before_request(self, endpoint: str, attempt: int) -> None:
        if self.result.request_count >= self.max_requests:
            self.result.budget_exhausted = True
            raise _RequestBudgetExhausted
        ok = await self.context.progress(
            f"JustOneAPI request {self.result.request_count + 1}/{self.max_requests}: {endpoint}",
            stage="provider_request",
        )
        if not ok:
            raise ExecutorLeaseLost
        self.result.request_count += 1
        self.checkpoint["request_count"] = self.result.request_count
        if not await self.context.checkpoint(dict(self.checkpoint)):
            raise ExecutorLeaseLost
        self._inflight_request_id = await db.record_provider_request(
            task_id=self.context.task_id,
            provider=db.TaskProvider.JUSTONEAPI,
            endpoint=endpoint,
            attempt=attempt,
            request_state="inflight",
        )

    async def observe(self, record: RequestRecord) -> None:
        if record.billed:
            self.result.billed_success_count += 1
        self.checkpoint["billed_success_count"] = self.result.billed_success_count
        if self._inflight_request_id:
            await db.complete_provider_request(
                self._inflight_request_id,
                request_id=record.request_id,
                http_status=record.http_status,
                business_code=record.business_code,
                duration_ms=record.duration_ms,
                attempt=record.attempt,
                billed=record.billed,
                error_type=record.error_type,
                outcome_unknown=record.outcome_unknown,
            )
            self._inflight_request_id = None
        else:
            await db.record_provider_request(
                task_id=self.context.task_id,
                provider=db.TaskProvider.JUSTONEAPI,
                endpoint=record.endpoint,
                request_id=record.request_id,
                http_status=record.http_status,
                business_code=record.business_code,
                duration_ms=record.duration_ms,
                attempt=record.attempt,
                billed=record.billed,
                error_type=record.error_type,
                outcome_unknown=record.outcome_unknown,
            )
        if not await self.context.checkpoint(dict(self.checkpoint)):
            raise ExecutorLeaseLost


class JustOneApiTaskExecutor(TaskExecutor):
    provider = db.TaskProvider.JUSTONEAPI.value

    def __init__(
        self,
        client: JustOneApiClient,
        *,
        store: Optional[_Store] = None,
        normalizer: Optional[JustOneApiNormalizer] = None,
        enabled: Optional[bool] = None,
        max_requests_per_task: Optional[int] = None,
    ):
        self._client = client
        self._store = store or XhsStoreFactory.create_store()
        self._normalizer = normalizer or JustOneApiNormalizer()
        self._enabled = settings.justoneapi_enabled if enabled is None else bool(enabled)
        configured_limit = (
            settings.justoneapi_max_requests_per_task
            if max_requests_per_task is None
            else int(max_requests_per_task)
        )
        self._max_requests_per_task = max(1, configured_limit)
        self._blocked_reason: Optional[str] = None
        self._blocked_until: Optional[datetime] = None

    async def readiness(self) -> ProviderReadiness:
        self._clear_expired_block()
        if not self._enabled:
            return ProviderReadiness(enabled=False, ready=False, reason="disabled")
        if self._client.closed:
            return ProviderReadiness(enabled=True, ready=False, reason="client_closed")
        if not self._client.configured:
            return ProviderReadiness(enabled=True, ready=False, reason="missing_token")
        if self._blocked_reason:
            details: Dict[str, Any] = {}
            if self._blocked_until:
                details["blocked_until"] = self._blocked_until.isoformat()
            return ProviderReadiness(
                enabled=True,
                ready=False,
                reason=self._blocked_reason,
                details=details,
            )
        return ProviderReadiness(
            enabled=True,
            ready=True,
            details={
                "base_url": self._client.base_url,
                "timeout_sec": self._client.timeout_sec,
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def execute(
        self,
        task: Dict[str, Any],
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> Dict[str, Any]:
        readiness = await self.readiness()
        if not readiness.ready:
            raise ExecutorPaused(
                f"JustOneAPI provider is not ready: {readiness.reason}",
            )

        options = self._options(params)
        max_requests = min(
            options["max_requests"],
            self._max_requests_per_task,
        )
        checkpoint = task.get("checkpoint_json")
        if not isinstance(checkpoint, dict):
            checkpoint = {}
        expected_kind = {
            db.TaskType.SEARCH.value: "search",
            db.TaskType.CREATOR.value: "creator",
            db.TaskType.NOTE.value: "note",
        }.get(task["task_type"])
        if expected_kind is None:
            raise ValueError(f"Unknown task type: {task['task_type']}")
        if checkpoint.get("kind") not in {None, expected_kind}:
            checkpoint = {}
        checkpoint["kind"] = expected_kind
        result = CrawlResult(
            request_count=max(0, self._int(checkpoint.get("request_count"), 0)),
            billed_success_count=max(
                0,
                self._int(checkpoint.get("billed_success_count"), 0),
            ),
        )
        state = _RunState(context, max_requests, result, checkpoint)

        try:
            if task["task_type"] == db.TaskType.SEARCH.value:
                await self._execute_search(params, options, checkpoint, state)
            elif task["task_type"] == db.TaskType.CREATOR.value:
                await self._execute_creator(params, options, checkpoint, state)
            elif task["task_type"] == db.TaskType.NOTE.value:
                await self._execute_notes(params, options, checkpoint, state)
        except _RequestBudgetExhausted:
            result.budget_exhausted = True
        except JustOneApiError as exc:
            self._raise_for_provider_error(exc)

        result.checkpoint = dict(checkpoint)
        return result.as_dict()

    async def _execute_search(
        self,
        params: Dict[str, Any],
        options: Dict[str, Any],
        checkpoint: Dict[str, Any],
        state: _RunState,
    ) -> None:
        keyword = str(params["keyword"]).strip()
        if checkpoint.get("kind") not in {None, "search"}:
            checkpoint.clear()
        checkpoint["kind"] = "search"
        page = max(1, self._int(checkpoint.get("page"), 1))
        pages_completed = max(0, self._int(checkpoint.get("pages_completed"), 0))
        seen_note_ids = {str(value) for value in checkpoint.get("note_ids", []) if value}
        comments_count = max(0, self._int(checkpoint.get("comments_count"), 0))
        max_notes = max(1, self._int(params.get("max_notes"), 20))
        search_id = checkpoint.get("search_id")
        session_id = checkpoint.get("session_id")
        if options["include_comments"]:
            comments_count = await self._resume_checkpoint_comments(
                checkpoint,
                options,
                params,
                state,
                comments_count,
            )

        while pages_completed < options["max_pages"] and len(seen_note_ids) < max_notes:
            envelope = await self._call(
                state,
                self._client.search_notes,
                keyword,
                page=page,
                sort_type=params.get("sort_type", TRANSPORT_SORT_TYPE_DEFAULT),
                note_type=options["note_type"],
                time_filter=options["time_filter"],
                search_id=search_id,
                session_id=session_id,
            )
            if envelope is None:
                break
            items = self._normalizer.list_items(envelope.data)
            page_complete = True
            for item in items:
                if len(seen_note_ids) >= max_notes:
                    page_complete = False
                    break
                note = self._normalizer.note(item, source_keyword=keyword)
                if not note or note.note_id in seen_note_ids:
                    continue
                await self._store_note(note, state.context.task_id, keyword)
                if options["include_details"]:
                    detail = await self._note_detail(note, keyword, state)
                    if detail:
                        note = detail
                seen_note_ids.add(note.note_id)
                if options["include_comments"]:
                    checkpoint.setdefault("comment_notes", {})[
                        note.note_id
                    ] = note.to_store_dict()
                    await self._checkpoint(state.context, checkpoint)
                    new_comments = await self._crawl_comments(
                        note,
                        options,
                        params,
                        state,
                        checkpoint,
                    )
                    comments_count = max(
                        comments_count + new_comments,
                        self._checkpoint_comment_count(checkpoint),
                    )
                checkpoint.update(
                    {
                        "page": page,
                        "pages_completed": pages_completed,
                        "search_id": search_id,
                        "session_id": session_id,
                        "note_ids": sorted(seen_note_ids),
                        "comments_count": comments_count,
                    }
                )
                await self._checkpoint(state.context, checkpoint)
                await self._progress_counts(state, len(seen_note_ids), comments_count)

            if not page_complete:
                checkpoint.update(
                    {
                        "page": page,
                        "pages_completed": pages_completed,
                        "note_ids": sorted(seen_note_ids),
                        "comments_count": comments_count,
                    }
                )
                await self._checkpoint(state.context, checkpoint)
                break

            pagination = self._normalizer.pagination(envelope.data)
            pages_completed += 1
            page += 1
            search_id = pagination.get("search_id") or search_id
            session_id = pagination.get("session_id") or session_id
            checkpoint.update(
                {
                    "page": page,
                    "pages_completed": pages_completed,
                    "search_id": search_id,
                    "session_id": session_id,
                    "note_ids": sorted(seen_note_ids),
                    "comments_count": comments_count,
                }
            )
            await self._checkpoint(state.context, checkpoint)
            if not pagination["has_more"]:
                break

        state.result.notes_count = len(seen_note_ids)
        state.result.comments_count = comments_count

    async def _execute_creator(
        self,
        params: Dict[str, Any],
        options: Dict[str, Any],
        checkpoint: Dict[str, Any],
        state: _RunState,
    ) -> None:
        creator_input = str(params["creator_input"]).strip()
        if checkpoint.get("kind") not in {None, "creator"}:
            checkpoint.clear()
        checkpoint["kind"] = "creator"
        user_id = str(checkpoint.get("user_id") or "").strip()
        if not user_id:
            user_id = await self._resolve_creator_id(creator_input, state)
            if not user_id:
                raise ValueError("Could not resolve creator ID from input.")
            checkpoint["user_id"] = user_id

        if not checkpoint.get("profile_completed"):
            profile_envelope = await self._call(state, self._client.user_profile, user_id)
            if profile_envelope is None:
                return
            creator = self._normalizer.creator(
                profile_envelope.data,
                fallback_user_id=user_id,
            )
            if not creator:
                raise JustOneApiProtocolError(
                    "user profile response did not contain a creator",
                    endpoint=profile_envelope.endpoint,
                    request_id=profile_envelope.request_id,
                )
            await self._store.store_creator(
                creator.to_store_dict(),
                provider=self.provider,
                task_id=state.context.task_id,
            )
            state.result.creators_count = 1
            checkpoint["profile_completed"] = True
            await self._checkpoint(state.context, checkpoint)

        cursor = checkpoint.get("cursor")
        pages_completed = max(0, self._int(checkpoint.get("pages_completed"), 0))
        seen_note_ids = {str(value) for value in checkpoint.get("note_ids", []) if value}
        comments_count = max(0, self._int(checkpoint.get("comments_count"), 0))
        max_notes = max(1, self._int(params.get("max_notes"), 20))
        if options["include_comments"]:
            comments_count = await self._resume_checkpoint_comments(
                checkpoint,
                options,
                params,
                state,
                comments_count,
            )

        while pages_completed < options["max_pages"] and len(seen_note_ids) < max_notes:
            envelope = await self._call(
                state,
                self._client.creator_notes,
                user_id,
                cursor=cursor,
            )
            if envelope is None:
                break
            items = self._normalizer.list_items(envelope.data)
            page_complete = True
            for item in items:
                if len(seen_note_ids) >= max_notes:
                    page_complete = False
                    break
                note = self._normalizer.note(item)
                if not note or note.note_id in seen_note_ids:
                    continue
                await self._store_note(note, state.context.task_id, "")
                if options["include_details"]:
                    detail = await self._note_detail(note, "", state)
                    if detail:
                        note = detail
                seen_note_ids.add(note.note_id)
                if options["include_comments"]:
                    checkpoint.setdefault("comment_notes", {})[
                        note.note_id
                    ] = note.to_store_dict()
                    await self._checkpoint(state.context, checkpoint)
                    new_comments = await self._crawl_comments(
                        note,
                        options,
                        params,
                        state,
                        checkpoint,
                    )
                    comments_count = max(
                        comments_count + new_comments,
                        self._checkpoint_comment_count(checkpoint),
                    )
                checkpoint.update(
                    {
                        "cursor": cursor,
                        "pages_completed": pages_completed,
                        "note_ids": sorted(seen_note_ids),
                        "comments_count": comments_count,
                    }
                )
                await self._checkpoint(state.context, checkpoint)
                await self._progress_counts(state, len(seen_note_ids), comments_count)

            if not page_complete:
                checkpoint.update(
                    {
                        "cursor": cursor,
                        "pages_completed": pages_completed,
                        "note_ids": sorted(seen_note_ids),
                        "comments_count": comments_count,
                    }
                )
                await self._checkpoint(state.context, checkpoint)
                break

            pagination = self._normalizer.pagination(envelope.data)
            next_cursor = pagination.get("cursor")
            pages_completed += 1
            checkpoint.update(
                {
                    "cursor": next_cursor,
                    "pages_completed": pages_completed,
                    "note_ids": sorted(seen_note_ids),
                    "comments_count": comments_count,
                }
            )
            await self._checkpoint(state.context, checkpoint)
            if not pagination["has_more"] or not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor

        state.result.notes_count = len(seen_note_ids)
        state.result.comments_count = comments_count
        state.result.creators_count = 1 if checkpoint.get("profile_completed") else 0

    async def _execute_notes(
        self,
        params: Dict[str, Any],
        options: Dict[str, Any],
        checkpoint: Dict[str, Any],
        state: _RunState,
    ) -> None:
        if checkpoint.get("kind") not in {None, "note"}:
            checkpoint.clear()
        checkpoint["kind"] = "note"
        processed = {str(value) for value in checkpoint.get("note_ids", []) if value}
        comments_count = max(0, self._int(checkpoint.get("comments_count"), 0))
        if options["include_comments"]:
            comments_count = await self._resume_checkpoint_comments(
                checkpoint,
                options,
                params,
                state,
                comments_count,
            )

        for item in params.get("notes", []):
            note_input = str(item.get("note_input", "")).strip()
            note_id = self._normalizer.note_id(note_input)
            if not note_id and note_input.startswith("http"):
                note_id = await self._resolve_note_id(note_input, state)
            if not note_id:
                raise ValueError(f"Could not resolve note ID: {note_input}")
            if note_id in processed:
                continue
            envelope = await self._call(state, self._client.note_detail, note_id)
            if envelope is None:
                break
            detail_item = self._detail_item(envelope.data)
            note = self._normalizer.note(detail_item)
            if not note:
                raise ValueError(f"JustOneAPI note detail did not contain note {note_id}.")
            await self._store_note(note, state.context.task_id, "")
            processed.add(note.note_id)
            await db.upsert_note_tag(
                note.note_id,
                str(item.get("d_level", "")),
                str(item.get("quality", "")),
            )
            if options["include_comments"]:
                checkpoint.setdefault("comment_notes", {})[
                    note.note_id
                ] = note.to_store_dict()
                await self._checkpoint(state.context, checkpoint)
                new_comments = await self._crawl_comments(
                    note,
                    options,
                    params,
                    state,
                    checkpoint,
                )
                comments_count = max(
                    comments_count + new_comments,
                    self._checkpoint_comment_count(checkpoint),
                )
            checkpoint.update(
                {
                    "note_ids": sorted(processed),
                    "comments_count": comments_count,
                }
            )
            await self._checkpoint(state.context, checkpoint)
            await self._progress_counts(state, len(processed), comments_count)

        state.result.notes_count = len(processed)
        state.result.comments_count = comments_count

    async def _note_detail(
        self,
        note: CanonicalNote,
        source_keyword: str,
        state: _RunState,
    ) -> Optional[CanonicalNote]:
        envelope = await self._call(
            state,
            self._client.note_detail,
            note.note_id,
            xsec_token=note.xsec_token or None,
        )
        if envelope is None:
            return None
        detail = self._normalizer.note(
            self._detail_item(envelope.data),
            source_keyword=source_keyword,
        )
        if not detail:
            raise JustOneApiProtocolError(
                "note detail response did not contain a note",
                endpoint=envelope.endpoint,
                request_id=envelope.request_id,
            )
        await self._store_note(detail, state.context.task_id, source_keyword)
        return detail

    async def _resume_checkpoint_comments(
        self,
        checkpoint: Dict[str, Any],
        options: Dict[str, Any],
        params: Dict[str, Any],
        state: _RunState,
        comments_count: int,
    ) -> int:
        raw_notes = checkpoint.get("comment_notes")
        if not isinstance(raw_notes, dict):
            return comments_count
        for note_id, raw_note in list(raw_notes.items()):
            if not isinstance(raw_note, dict):
                continue
            if self._comments_satisfied(checkpoint, str(note_id), options, params):
                continue
            try:
                note = CanonicalNote(**raw_note)
            except TypeError:
                continue
            new_comments = await self._crawl_comments(
                note,
                options,
                params,
                state,
                checkpoint,
            )
            comments_count = max(
                comments_count + new_comments,
                self._checkpoint_comment_count(checkpoint),
            )
            checkpoint["comments_count"] = comments_count
            await self._checkpoint(state.context, checkpoint)
            if state.result.budget_exhausted:
                break
        return comments_count

    @staticmethod
    def _comments_satisfied(
        checkpoint: Dict[str, Any],
        note_id: str,
        options: Dict[str, Any],
        params: Dict[str, Any],
    ) -> bool:
        max_comments = max(0, JustOneApiTaskExecutor._int(params.get("max_comments"), 20))
        if max_comments == 0:
            return True
        progress_map = checkpoint.get("comment_progress")
        progress = progress_map.get(note_id) if isinstance(progress_map, dict) else None
        if not isinstance(progress, dict):
            return False
        if progress.get("completed"):
            return True
        comment_count = len({value for value in progress.get("comment_ids", []) if value})
        if comment_count >= max_comments:
            return True
        return (
            JustOneApiTaskExecutor._int(progress.get("pages_completed"), 0)
            >= options["max_pages"]
        )

    async def _crawl_comments(
        self,
        note: CanonicalNote,
        options: Dict[str, Any],
        params: Dict[str, Any],
        state: _RunState,
        checkpoint: Dict[str, Any],
    ) -> int:
        all_progress = checkpoint.setdefault("comment_progress", {})
        raw_progress = all_progress.get(note.note_id)
        note_progress = raw_progress if isinstance(raw_progress, dict) else {}
        all_progress[note.note_id] = note_progress
        if note_progress.get("completed"):
            return 0
        cursor = note_progress.get("cursor")
        pages_completed = max(0, self._int(note_progress.get("pages_completed"), 0))
        seen_comment_ids = {
            str(value) for value in note_progress.get("comment_ids", []) if value
        }
        initial_count = len(seen_comment_ids)
        reply_roots = {
            str(value) for value in note_progress.get("reply_roots", []) if value
        }
        replies_completed = {
            str(value)
            for value in note_progress.get("replies_completed", [])
            if value
        }
        max_comments = max(0, self._int(params.get("max_comments"), 20))
        if max_comments == 0 or len(seen_comment_ids) >= max_comments:
            return 0
        while pages_completed < options["max_pages"]:
            envelope = await self._call(
                state,
                self._client.comments,
                note.note_id,
                cursor=cursor,
                xsec_token=note.xsec_token or None,
            )
            if envelope is None:
                return len(seen_comment_ids) - initial_count
            page_complete = True
            for item in self._normalizer.list_items(envelope.data, comments=True):
                if len(seen_comment_ids) >= max_comments:
                    page_complete = False
                    break
                comment = self._normalizer.comment(item, note_id=note.note_id)
                if not comment or comment.comment_id in seen_comment_ids:
                    continue
                await self._store.store_comment(
                    comment.to_store_dict(),
                    provider=self.provider,
                    task_id=state.context.task_id,
                )
                seen_comment_ids.add(comment.comment_id)
                if options["include_replies"] and comment.sub_comment_count != 0:
                    reply_roots.add(comment.comment_id)
                note_progress.update(
                    {
                        "cursor": cursor,
                        "pages_completed": pages_completed,
                        "comment_ids": sorted(seen_comment_ids),
                        "reply_roots": sorted(reply_roots),
                        "replies_completed": sorted(replies_completed),
                    }
                )
                await self._checkpoint(state.context, checkpoint)
            if options["include_replies"]:
                for root_comment_id in sorted(reply_roots - replies_completed):
                    if len(seen_comment_ids) >= max_comments:
                        break
                    replies_done = await self._crawl_replies(
                        note,
                        root_comment_id,
                        options,
                        max_comments,
                        state,
                        checkpoint,
                        note_progress,
                        seen_comment_ids,
                    )
                    if replies_done:
                        replies_completed.add(root_comment_id)
                        note_progress["replies_completed"] = sorted(replies_completed)
                    await self._checkpoint(state.context, checkpoint)
                    if state.result.budget_exhausted:
                        break
            if not page_complete:
                note_progress.update(
                    {
                        "cursor": cursor,
                        "pages_completed": pages_completed,
                        "comment_ids": sorted(seen_comment_ids),
                    }
                )
                await self._checkpoint(state.context, checkpoint)
                break
            pagination = self._normalizer.pagination(envelope.data)
            next_cursor = pagination.get("cursor")
            pages_completed += 1
            note_progress.update(
                {
                    "cursor": next_cursor,
                    "pages_completed": pages_completed,
                    "comment_ids": sorted(seen_comment_ids),
                    "reply_roots": sorted(reply_roots),
                    "replies_completed": sorted(replies_completed),
                }
            )
            await self._checkpoint(state.context, checkpoint)
            if len(seen_comment_ids) >= max_comments or not pagination["has_more"]:
                note_progress["completed"] = True
                await self._checkpoint(state.context, checkpoint)
                break
            if not next_cursor or next_cursor == cursor:
                note_progress["completed"] = True
                await self._checkpoint(state.context, checkpoint)
                break
            cursor = next_cursor
        return len(seen_comment_ids) - initial_count

    async def _crawl_replies(
        self,
        note: CanonicalNote,
        root_comment_id: str,
        options: Dict[str, Any],
        max_comments: int,
        state: _RunState,
        checkpoint: Dict[str, Any],
        note_progress: Dict[str, Any],
        seen_comment_ids: set[str],
    ) -> bool:
        reply_progress_map = note_progress.setdefault("reply_progress", {})
        raw_progress = reply_progress_map.get(root_comment_id)
        reply_progress = raw_progress if isinstance(raw_progress, dict) else {}
        reply_progress_map[root_comment_id] = reply_progress
        cursor = reply_progress.get("cursor")
        pages_completed = max(0, self._int(reply_progress.get("pages_completed"), 0))
        while pages_completed < options["max_pages"]:
            envelope = await self._call(
                state,
                self._client.replies,
                note.note_id,
                root_comment_id,
                cursor=cursor,
                xsec_token=note.xsec_token or None,
            )
            if envelope is None:
                return False
            for item in self._normalizer.list_items(envelope.data, comments=True):
                if len(seen_comment_ids) >= max_comments:
                    break
                comment = self._normalizer.comment(item, note_id=note.note_id)
                if not comment or comment.comment_id in seen_comment_ids:
                    continue
                if not comment.parent_comment_id:
                    comment = replace(comment, parent_comment_id=root_comment_id)
                await self._store.store_comment(
                    comment.to_store_dict(),
                    provider=self.provider,
                    task_id=state.context.task_id,
                )
                seen_comment_ids.add(comment.comment_id)
                note_progress["comment_ids"] = sorted(seen_comment_ids)
                reply_progress.update(
                    {"cursor": cursor, "pages_completed": pages_completed}
                )
                await self._checkpoint(state.context, checkpoint)
            pagination = self._normalizer.pagination(envelope.data)
            next_cursor = pagination.get("cursor")
            pages_completed += 1
            reply_progress.update(
                {"cursor": next_cursor, "pages_completed": pages_completed}
            )
            await self._checkpoint(state.context, checkpoint)
            if not pagination["has_more"]:
                return True
            if len(seen_comment_ids) >= max_comments:
                return False
            if not next_cursor or next_cursor == cursor:
                return True
            cursor = next_cursor
        return False

    async def _call(self, state: _RunState, method, *args, **kwargs) -> Optional[ApiEnvelope]:
        try:
            envelope = await method(
                *args,
                **kwargs,
                observer=state.observe,
                before_request=state.before_request,
            )
        except _RequestBudgetExhausted:
            state.result.budget_exhausted = True
            return None
        if envelope.code != 0:
            raise error_from_envelope(envelope)
        return envelope

    async def _resolve_note_id(self, url: str, state: _RunState) -> Optional[str]:
        envelope = await self._call(state, self._client.resolve_share_link, url)
        if envelope is None:
            return None
        resolved = self._normalizer.resolved_url(envelope.data)
        return self._normalizer.note_id(resolved or "")

    async def _resolve_creator_id(self, value: str, state: _RunState) -> Optional[str]:
        creator_id = self._normalizer.creator_id(value)
        if creator_id:
            return creator_id
        if value.startswith("http"):
            envelope = await self._call(state, self._client.resolve_share_link, value)
            if envelope is None:
                return None
            resolved = self._normalizer.resolved_url(envelope.data)
            return self._normalizer.creator_id(resolved or "")
        return None

    async def _store_note(self, note: CanonicalNote, task_id: int, keyword: str) -> None:
        await self._store.store_content(
            note.to_store_dict(),
            provider=self.provider,
            task_id=task_id,
            source_keyword=keyword,
        )

    async def _progress_counts(
        self,
        state: _RunState,
        notes_count: int,
        comments_count: int,
    ) -> None:
        ok = await state.context.progress(
            f"JustOneAPI stored {notes_count} notes and {comments_count} comments",
            stage="persisting",
            notes_count=notes_count,
            comments_count=comments_count,
        )
        if not ok:
            raise ExecutorLeaseLost

    @staticmethod
    async def _checkpoint(context: ExecutionContext, checkpoint: Dict[str, Any]) -> None:
        if not await context.checkpoint(dict(checkpoint)):
            raise ExecutorLeaseLost

    def _raise_for_provider_error(self, exc: JustOneApiError) -> None:
        retry_after = exc.retry_after_seconds
        if isinstance(
            exc,
            (
                JustOneApiCredentialError,
                JustOneApiBalanceError,
                JustOneApiTokenLimitError,
            ),
        ):
            self._blocked_reason = exc.category
            self._blocked_until = None
            raise ExecutorPaused(str(exc), error=str(exc)) from exc
        if isinstance(exc, (JustOneApiRateLimitError, JustOneApiDailyQuotaError)):
            retry_after = retry_after or 60.0
            self._blocked_reason = exc.category
            self._blocked_until = datetime.now() + timedelta(seconds=retry_after)
            raise ExecutorPaused(
                str(exc),
                error=str(exc),
                retry_after_seconds=retry_after,
            ) from exc
        if isinstance(
            exc,
            (JustOneApiUpstreamError, JustOneApiTransportError, JustOneApiHttpError),
        ):
            raise ExecutorPaused(
                str(exc),
                error=str(exc),
                retry_after_seconds=retry_after or 30.0,
            ) from exc
        raise exc

    def _clear_expired_block(self) -> None:
        if self._blocked_until and datetime.now() >= self._blocked_until:
            self._blocked_until = None
            self._blocked_reason = None

    @staticmethod
    def _detail_item(data: Any) -> Any:
        items = JustOneApiNormalizer.list_items(data)
        if items:
            return items[0]
        if isinstance(data, Mapping):
            nested = data.get("data")
            return nested if isinstance(nested, Mapping) else data
        return data

    @staticmethod
    def _checkpoint_comment_count(checkpoint: Dict[str, Any]) -> int:
        progress = checkpoint.get("comment_progress")
        if not isinstance(progress, dict):
            return 0
        comment_ids: set[str] = set()
        for item in progress.values():
            if not isinstance(item, dict):
                continue
            comment_ids.update(
                str(value) for value in item.get("comment_ids", []) if value
            )
        return len(comment_ids)

    @staticmethod
    def _options(params: Dict[str, Any]) -> Dict[str, Any]:
        raw = params.get("provider_options")
        options = raw if isinstance(raw, dict) else {}
        return {
            "include_details": bool(
                options.get("include_details", TASK_OPTION_DEFAULTS.include_details)
            ),
            "include_comments": bool(
                options.get("include_comments", TASK_OPTION_DEFAULTS.include_comments)
            ),
            "include_replies": bool(
                options.get("include_replies", TASK_OPTION_DEFAULTS.include_replies)
            ),
            "max_pages": max(
                PAGE_LIMIT_MIN,
                min(
                    PAGE_LIMIT_MAX,
                    JustOneApiTaskExecutor._int(
                        options.get("max_pages"),
                        TASK_OPTION_DEFAULTS.max_pages,
                    ),
                ),
            ),
            "max_requests": max(
                REQUEST_BUDGET_MIN,
                min(
                    REQUEST_BUDGET_MAX,
                    JustOneApiTaskExecutor._int(
                        options.get("max_requests"),
                        TASK_OPTION_DEFAULTS.max_requests,
                    ),
                ),
            ),
            "note_type": str(
                options.get("note_type", TASK_OPTION_DEFAULTS.note_type)
            ),
            "time_filter": str(
                options.get("time_filter", TASK_OPTION_DEFAULTS.time_filter)
            ),
        }

    @staticmethod
    def _int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
