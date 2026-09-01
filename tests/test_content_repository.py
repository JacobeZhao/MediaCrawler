import asyncio
import os
import tempfile
import unittest

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine

from database import db_session
from database.models import XhsContentSource, XhsCreator, XhsNote, XhsNoteComment
from store import xhs as xhs_store
from store.xhs._store_impl import XhsSqliteStoreImplement
from var import source_keyword_var


class _TemporaryDatabaseTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db_path = os.path.join(self._temp_dir.name, "content.db")
        self._engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_path}",
            connect_args={"timeout": 5},
        )
        self._previous_engine = db_session._engines.get("sqlite")
        db_session._engines["sqlite"] = self._engine

    async def asyncTearDown(self):
        await self._engine.dispose()
        if self._previous_engine is None:
            db_session._engines.pop("sqlite", None)
        else:
            db_session._engines["sqlite"] = self._previous_engine
        self._temp_dir.cleanup()


class DatabaseEngineLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispose_engines_releases_and_clears_cached_engines(self):
        class FakeEngine:
            disposed = False

            async def dispose(self):
                self.disposed = True

        previous_engines = dict(db_session._engines)
        previous_initialized = list(db_session._initialized_schema_engines)
        db_session._engines.clear()
        db_session._initialized_schema_engines.clear()
        try:
            engine = FakeEngine()
            db_session._engines["test"] = engine
            db_session._initialized_schema_engines.add(engine)

            await db_session.dispose_engines()

            self.assertTrue(engine.disposed)
            self.assertEqual({}, db_session._engines)
            self.assertNotIn(engine, db_session._initialized_schema_engines)
        finally:
            db_session._engines.update(previous_engines)
            db_session._initialized_schema_engines.update(previous_initialized)


class ContentRepositoryTests(_TemporaryDatabaseTest):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await db_session.create_tables("sqlite")
        self.store = XhsSqliteStoreImplement()

    async def test_note_upsert_preserves_non_empty_data_and_tracks_sources(self):
        await self.store.store_content(
            {
                "note_id": "note-1",
                "title": "complete title",
                "desc": "complete description",
                "liked_count": 12,
                "comment_count": 3,
                "image_list": ["https://img/1.jpg"],
                "source_keyword": "coffee",
            },
            provider="justoneapi",
            task_id=41,
        )
        await self.store.store_content(
            {
                "note_id": "note-1",
                "title": "",
                "desc": None,
                "liked_count": 0,
                "comment_count": 8,
                "image_list": [],
                "source_keyword": "coffee",
            },
            provider="justoneapi",
            task_id=41,
        )
        await self.store.store_content(
            {"note_id": "note-1", "share_count": 2},
            provider="local",
            task_id=42,
            source_keyword="coffee",
        )

        async with db_session.get_session() as session:
            notes = (await session.execute(select(XhsNote))).scalars().all()
            sources = (await session.execute(select(XhsContentSource))).scalars().all()

        self.assertEqual(1, len(notes))
        self.assertEqual("complete title", notes[0].title)
        self.assertEqual("complete description", notes[0].desc)
        self.assertEqual("0", notes[0].liked_count)
        self.assertEqual("8", notes[0].comment_count)
        self.assertIn("https://img/1.jpg", notes[0].image_list)
        self.assertEqual(2, len(sources))
        self.assertEqual({"justoneapi", "local"}, {source.provider for source in sources})

    async def test_comment_and_creator_upserts_do_not_erase_complete_fields(self):
        await self.store.store_comment(
            {
                "comment_id": "comment-1",
                "note_id": "note-1",
                "content": "useful comment",
                "nickname": "commenter",
                "like_count": 4,
                "sub_comment_count": 2,
            },
            provider="justoneapi",
            task_id=51,
        )
        await self.store.store_comment(
            {
                "comment_id": "comment-1",
                "note_id": "",
                "content": None,
                "nickname": "",
                "like_count": 0,
                "sub_comment_count": 0,
            },
            provider="justoneapi",
            task_id=51,
        )
        await self.store.store_creator(
            {
                "user_id": "user-1",
                "nickname": "creator",
                "desc": "profile",
                "fans": 9,
            },
            provider="justoneapi",
            task_id=51,
        )
        await self.store.store_creator(
            {"user_id": "user-1", "nickname": "", "desc": None, "fans": 0},
            provider="justoneapi",
            task_id=51,
        )

        async with db_session.get_session() as session:
            comments = (await session.execute(select(XhsNoteComment))).scalars().all()
            creators = (await session.execute(select(XhsCreator))).scalars().all()

        self.assertEqual(1, len(comments))
        self.assertEqual("note-1", comments[0].note_id)
        self.assertEqual("useful comment", comments[0].content)
        self.assertEqual("commenter", comments[0].nickname)
        self.assertEqual("0", comments[0].like_count)
        self.assertEqual(0, comments[0].sub_comment_count)
        self.assertEqual(1, len(creators))
        self.assertEqual("creator", creators[0].nickname)
        self.assertEqual("profile", creators[0].desc)
        self.assertEqual("0", creators[0].fans)

    async def test_concurrent_writes_are_idempotent(self):
        await asyncio.gather(
            *(
                self.store.store_content(
                    {"note_id": "note-race", "title": f"title-{index}"},
                    provider="justoneapi",
                    task_id=60,
                )
                for index in range(8)
            )
        )

        async with db_session.get_session() as session:
            count = await session.scalar(
                select(func.count()).select_from(XhsNote).where(XhsNote.note_id == "note-race")
            )
            source_count = await session.scalar(
                select(func.count())
                .select_from(XhsContentSource)
                .where(XhsContentSource.entity_id == "note-race")
            )

        self.assertEqual(1, count)
        self.assertEqual(1, source_count)

    async def test_legacy_nested_store_entrypoint_remains_compatible(self):
        keyword_token = source_keyword_var.set("legacy-keyword")
        try:
            with self.assertLogs("MediaCrawler", level="INFO") as captured:
                await xhs_store.update_xhs_note(
                    {
                        "note_id": "legacy-note",
                        "type": "normal",
                        "title": "legacy title",
                        "desc": "legacy description",
                        "time": 1700000000000,
                        "last_update_time": 1700000000001,
                        "user": {
                            "user_id": "legacy-user",
                            "nickname": "legacy creator",
                        },
                        "interact_info": {"liked_count": 1, "comment_count": 2},
                        "image_list": [{"url_default": "https://img/legacy.jpg"}],
                        "tag_list": [{"type": "topic", "name": "legacy"}],
                        "xsec_token": "legacy-token",
                    }
                )
        finally:
            source_keyword_var.reset(keyword_token)

        rendered_logs = "\n".join(captured.output)
        self.assertIn("note_id=legacy-note", rendered_logs)
        self.assertNotIn("legacy-token", rendered_logs)
        self.assertNotIn("legacy description", rendered_logs)

        async with db_session.get_session() as session:
            note = await session.scalar(
                select(XhsNote).where(XhsNote.note_id == "legacy-note")
            )
            source = await session.scalar(
                select(XhsContentSource).where(
                    XhsContentSource.entity_id == "legacy-note"
                )
            )

        self.assertEqual("legacy title", note.title)
        self.assertEqual("local", source.provider)
        self.assertEqual(0, source.task_id)
        self.assertEqual("legacy-keyword", source.source_keyword)


class ContentSchemaMigrationTests(_TemporaryDatabaseTest):
    async def test_legacy_duplicates_are_merged_before_unique_index_creation(self):
        async with self._engine.begin() as conn:
            await conn.exec_driver_sql(
                "CREATE TABLE xhs_note ("
                "id INTEGER PRIMARY KEY, note_id VARCHAR(255), title TEXT, desc TEXT, "
                "add_ts BIGINT, last_modify_ts BIGINT)"
            )
            await conn.exec_driver_sql(
                "CREATE INDEX ix_xhs_note_note_id ON xhs_note (note_id)"
            )
            await conn.exec_driver_sql(
                "INSERT INTO xhs_note "
                "(id, note_id, title, desc, add_ts, last_modify_ts) VALUES "
                "(1, 'duplicate', 'older title', 'older description', 1, 10), "
                "(2, 'duplicate', '', NULL, 2, 20)"
            )

        await db_session.create_tables("sqlite")

        async with self._engine.connect() as conn:
            rows = (
                await conn.exec_driver_sql(
                    "SELECT note_id, title, desc FROM xhs_note WHERE note_id='duplicate'"
                )
            ).mappings().all()
            indexes = (
                await conn.exec_driver_sql("PRAGMA index_list('xhs_note')")
            ).mappings().all()

        self.assertEqual(
            [{"note_id": "duplicate", "title": "older title", "desc": "older description"}],
            [dict(row) for row in rows],
        )
        self.assertTrue(any(index["unique"] for index in indexes))


if __name__ == "__main__":
    unittest.main()
