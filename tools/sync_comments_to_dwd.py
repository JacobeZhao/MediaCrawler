"""Sync ODS XHS comments into DWD comment thread table.

This ETL keeps one DWD row per top-level comment and preserves existing
AI/manual labels when re-running.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from typing import Iterable

import pymysql


DEFAULT_KEYWORDS = [
    "米粉推荐婴儿",
    "小皮高铁侠米粉",
    "核桃油",
    "宝宝果泥",
    "宝宝辅食",
    "宝宝面条",
]


def load_env(path: str = ".env") -> dict[str, str]:
    env: dict[str, str] = {}
    if not os.path.exists(path):
        return env
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    return env


def connect():
    env = load_env()
    return pymysql.connect(
        host=env["MYSQL_HOST"],
        port=int(env.get("MYSQL_PORT", "3306")),
        user=env["MYSQL_USER"],
        password=env["MYSQL_PASSWORD"],
        database="ai_platform",
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def parse_keywords(raw: str | None) -> list[str]:
    if not raw:
        return DEFAULT_KEYWORDS
    return [item.strip() for item in raw.split(",") if item.strip()]


def placeholders(values: Iterable[object]) -> str:
    return ",".join(["%s"] * len(list(values)))


def count_source_rows(cur, keywords: list[str]) -> tuple[int, int]:
    ph = ",".join(["%s"] * len(keywords))
    cur.execute(
        f"""
        SELECT COUNT(*) AS cnt
        FROM ods_xhs_comments_di c
        WHERE COALESCE(c.source_keyword, '') IN ({ph})
          AND c.comment_id IS NOT NULL
          AND c.comment_id <> ''
          AND c.note_id IS NOT NULL
          AND c.note_id <> ''
          AND NULLIF(TRIM(c.content), '') IS NOT NULL
          AND (
            c.comment_level = 1
            OR c.parent_comment_id IS NULL
            OR c.parent_comment_id = ''
            OR c.parent_comment_id = '0'
          )
        """,
        keywords,
    )
    top_level = int(cur.fetchone()["cnt"])
    cur.execute(
        f"""
        SELECT COUNT(*) AS cnt
        FROM ods_xhs_comments_di c
        WHERE COALESCE(c.source_keyword, '') IN ({ph})
        """,
        keywords,
    )
    all_comments = int(cur.fetchone()["cnt"])
    return top_level, all_comments


def sync_comments(cur, keywords: list[str], limit: int | None = None) -> int:
    ph = ",".join(["%s"] * len(keywords))
    limit_sql = f" LIMIT {int(limit)}" if limit else ""
    # Use comment source period dimension first; keyword dimension can duplicate
    # categories for the same keyword, so keep it as a fallback with a grouped
    # single row per keyword.
    sql = f"""
    INSERT INTO dwd_xhs_comment_threads_df (
      comment_id,
      content,
      thread_text,
      label_id,
      label_name,
      l1_tag_id,
      l1_tag_name,
      l2_tag_id,
      l2_tag_name,
      l3_tag_name,
      is_valuable,
      reply_cnt,
      note_id,
      note_title,
      note_publish_time,
      user_id,
      nickname,
      create_time,
      ip_location,
      process_time,
      source_keyword,
      keyword_category,
      keyword_update_cycle,
      keyword_period_label
    )
    SELECT
      c.comment_id,
      LEFT(NULLIF(TRIM(c.content), ''), 1024) AS content,
      LEFT(
        CASE
          WHEN replies.reply_text IS NULL OR replies.reply_text = '' THEN CONCAT('主评论：', NULLIF(TRIM(c.content), ''))
          ELSE CONCAT('主评论：', NULLIF(TRIM(c.content), ''), '\n', replies.reply_text)
        END,
        60000
      ) AS thread_text,
      c.label_id,
      c.label_name,
      NULL AS l1_tag_id,
      NULL AS l1_tag_name,
      NULL AS l2_tag_id,
      NULL AS l2_tag_name,
      NULL AS l3_tag_name,
      CASE
        WHEN c.pain_score IS NOT NULL AND c.pain_score >= 6 THEN 1
        WHEN c.label_id IS NOT NULL AND c.label_id NOT IN (8, 9, 10) THEN 1
        ELSE 0
      END AS is_valuable,
      COALESCE(replies.reply_cnt, 0) AS reply_cnt,
      c.note_id,
      LEFT(COALESCE(NULLIF(c.note_title, ''), n.title), 512) AS note_title,
      COALESCE(c.note_publish_time, n.publish_time) AS note_publish_time,
      c.user_id,
      c.nickname,
      c.create_time,
      c.ip_location,
      NOW() AS process_time,
      COALESCE(NULLIF(c.source_keyword, ''), n.source_keyword) AS source_keyword,
      COALESCE(sp.category, kp.category, c.keyword_category) AS keyword_category,
      COALESCE(sp.update_cycle, kp.update_cycle, c.keyword_update_cycle, 'monthly') AS keyword_update_cycle,
      COALESCE(sp.period_label, kp.period_label, c.keyword_period_label) AS keyword_period_label
    FROM ods_xhs_comments_di c
    LEFT JOIN ods_xhs_notes_di n
      ON n.note_id = c.note_id
    LEFT JOIN (
      SELECT
        r.parent_comment_id,
        COUNT(DISTINCT r.comment_id) AS reply_cnt,
        GROUP_CONCAT(
          CONCAT('回复：', NULLIF(TRIM(r.content), ''))
          ORDER BY r.create_time ASC, r.comment_id ASC
          SEPARATOR '\n'
        ) AS reply_text
      FROM ods_xhs_comments_di r
      WHERE r.parent_comment_id IS NOT NULL
        AND r.parent_comment_id <> ''
        AND r.parent_comment_id <> '0'
        AND r.comment_id IS NOT NULL
        AND r.comment_id <> ''
        AND NULLIF(TRIM(r.content), '') IS NOT NULL
      GROUP BY r.parent_comment_id
    ) replies
      ON replies.parent_comment_id = c.comment_id
    LEFT JOIN (
      SELECT
        source_keyword,
        MIN(category) AS category,
        MIN(update_cycle) AS update_cycle,
        MIN(period_label) AS period_label,
        MIN(active_from) AS active_from,
        MAX(active_to) AS active_to
      FROM dim_xhs_comment_source_period_df
      WHERE update_cycle = 'monthly'
      GROUP BY source_keyword
    ) sp
      ON sp.source_keyword COLLATE utf8mb4_unicode_ci = COALESCE(NULLIF(c.source_keyword, ''), n.source_keyword)
     AND sp.update_cycle = 'monthly'
     AND (sp.active_to IS NULL OR sp.active_to >= DATE(COALESCE(c.process_time, NOW())))
     AND sp.active_from <= DATE(COALESCE(c.process_time, NOW()))
    LEFT JOIN (
      SELECT keyword, MIN(category) AS category, MIN(update_cycle) AS update_cycle, MIN(period_label) AS period_label
      FROM dim_xhs_keyword_period_df
      WHERE update_cycle = 'monthly'
      GROUP BY keyword
    ) kp
      ON kp.keyword COLLATE utf8mb4_unicode_ci = COALESCE(NULLIF(c.source_keyword, ''), n.source_keyword)
    WHERE COALESCE(c.source_keyword, '') IN ({ph})
      AND c.comment_id IS NOT NULL
      AND c.comment_id <> ''
      AND c.note_id IS NOT NULL
      AND c.note_id <> ''
      AND NULLIF(TRIM(c.content), '') IS NOT NULL
      AND (
        c.comment_level = 1
        OR c.parent_comment_id IS NULL
        OR c.parent_comment_id = ''
        OR c.parent_comment_id = '0'
      )
    ORDER BY c.create_time ASC, c.comment_id ASC
    {limit_sql}
    ON DUPLICATE KEY UPDATE
      content = VALUES(content),
      thread_text = VALUES(thread_text),
      label_id = COALESCE(dwd_xhs_comment_threads_df.label_id, VALUES(label_id)),
      label_name = COALESCE(dwd_xhs_comment_threads_df.label_name, VALUES(label_name)),
      l1_tag_id = dwd_xhs_comment_threads_df.l1_tag_id,
      l1_tag_name = dwd_xhs_comment_threads_df.l1_tag_name,
      l2_tag_id = dwd_xhs_comment_threads_df.l2_tag_id,
      l2_tag_name = dwd_xhs_comment_threads_df.l2_tag_name,
      l3_tag_name = dwd_xhs_comment_threads_df.l3_tag_name,
      is_valuable = GREATEST(dwd_xhs_comment_threads_df.is_valuable, VALUES(is_valuable)),
      reply_cnt = VALUES(reply_cnt),
      note_id = VALUES(note_id),
      note_title = VALUES(note_title),
      note_publish_time = VALUES(note_publish_time),
      user_id = VALUES(user_id),
      nickname = VALUES(nickname),
      create_time = VALUES(create_time),
      ip_location = VALUES(ip_location),
      process_time = VALUES(process_time),
      source_keyword = VALUES(source_keyword),
      keyword_category = COALESCE(VALUES(keyword_category), dwd_xhs_comment_threads_df.keyword_category),
      keyword_update_cycle = COALESCE(VALUES(keyword_update_cycle), dwd_xhs_comment_threads_df.keyword_update_cycle),
      keyword_period_label = COALESCE(VALUES(keyword_period_label), dwd_xhs_comment_threads_df.keyword_period_label)
    """
    cur.execute(sql, keywords)
    return cur.rowcount


def verify(cur, keywords: list[str]) -> list[dict]:
    ph = ",".join(["%s"] * len(keywords))
    cur.execute(
        f"""
        SELECT source_keyword, keyword_category, keyword_update_cycle, keyword_period_label,
               COUNT(*) AS rows_cnt,
               SUM(reply_cnt) AS replies_cnt
        FROM dwd_xhs_comment_threads_df
        WHERE source_keyword IN ({ph})
        GROUP BY source_keyword, keyword_category, keyword_update_cycle, keyword_period_label
        ORDER BY source_keyword
        """,
        keywords,
    )
    return list(cur.fetchall())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keywords", help="Comma separated source_keyword list. Defaults to current crawl keywords.")
    parser.add_argument("--limit", type=int, help="Optional limit for testing.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    keywords = parse_keywords(args.keywords)
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SET SESSION group_concat_max_len = 1048576")
            top_level, all_comments = count_source_rows(cur, keywords)
            print(f"source_top_level={top_level} source_all_comments={all_comments}")
            if args.dry_run:
                conn.rollback()
                return 0
            affected = sync_comments(cur, keywords, args.limit)
            conn.commit()
            print(f"affected_rows={affected}")
            for row in verify(cur, keywords):
                print(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
