import json
import os
import re
from typing import List, Optional

import aiosqlite

from config.db_config import SQLITE_DB_PATH

_SAFE_NOTE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class NoteQueryService:
    def __init__(self, image_dir: str):
        self._image_dir = image_dir

    async def list_notes(
        self,
        keyword: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[dict]:
        if not os.path.exists(SQLITE_DB_PATH):
            return []

        conditions = []
        values: list = []
        if keyword:
            conditions.append("(source_keyword LIKE ? OR title LIKE ? OR desc LIKE ?)")
            pct = f"%{keyword}%"
            values.extend([pct, pct, pct])
        if user_id:
            conditions.append("user_id = ?")
            values.append(user_id)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        values.extend([limit, offset])

        async with aiosqlite.connect(SQLITE_DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"SELECT * FROM xhs_note {where} ORDER BY time DESC LIMIT ? OFFSET ?",
                values,
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_note_comments(self, note_id: str, limit: int = 200) -> List[dict]:
        if not os.path.exists(SQLITE_DB_PATH):
            return []

        async with aiosqlite.connect(SQLITE_DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM xhs_note_comment WHERE note_id = ? ORDER BY create_time ASC LIMIT ?",
                (note_id, limit),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    def list_note_images(self, note_id: str) -> List[str]:
        if not _SAFE_NOTE_ID_RE.match(note_id):
            return []
        root = os.path.abspath(self._image_dir)
        img_dir = os.path.abspath(os.path.join(root, note_id))
        if not img_dir.startswith(root + os.sep):
            return []
        if not os.path.isdir(img_dir):
            return []
        files = sorted(
            f for f in os.listdir(img_dir) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
        )
        return [f"/images/{note_id}/{f}" for f in files]


def parse_image_list(raw) -> List[str]:
    if not raw:
        return []
    text = str(raw).strip()
    try:
        decoded = json.loads(text)
    except Exception:
        decoded = text
    if isinstance(decoded, list):
        return [str(v).strip().strip('"').strip("'") for v in decoded if str(v).strip()]
    return [v.strip().strip('"').strip("'") for v in str(decoded).split(",") if v.strip()]
