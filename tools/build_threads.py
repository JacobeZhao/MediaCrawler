#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/build_threads.py
以一级评论为单位，聚合其下所有子孙评论，写入 xhs_comment_threads 表。

thread_text 格式（每级缩进2空格，从二级开始）：
  ↳ 用户A：评论内容
    ↳ 用户B：回复内容
      ↳ 用户A：再回复

用法：
  python tools/build_threads.py            # 增量构建（INSERT IGNORE，跳过已存在）
  python tools/build_threads.py --rebuild  # 清空表后重建
"""

import io
import os
import sys
import pymysql
import pymysql.cursors

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_DB = dict(
    host=os.environ.get("MYSQL_HOST", "120.24.236.119"),
    port=int(os.environ.get("MYSQL_PORT", "3306")),
    user=os.environ.get("MYSQL_USER", "ai_admin"),
    password=os.environ.get("MYSQL_PASSWORD", "AiAdmin@2026#123"),
    database=os.environ.get("MYSQL_DATABASE", "ai_platform"),
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
    connect_timeout=10,
)


def get_conn():
    return pymysql.connect(**_DB)


def build_thread_text(comment_id: str, children_map: dict, all_comments: dict, depth: int = 1) -> list[str]:
    """递归 DFS，返回当前节点所有子孙的缩进文本行列表。"""
    lines = []
    for child in children_map.get(comment_id, []):
        cid = child["comment_id"]
        indent = "  " * depth
        nickname = (child["nickname"] or "").replace("\n", " ")
        content = (child["content"] or "").replace("\n", " ")
        lines.append(f"{indent}↳ {nickname}：{content}")
        lines.extend(build_thread_text(cid, children_map, all_comments, depth + 1))
    return lines


def main():
    rebuild = "--rebuild" in sys.argv

    print("=" * 56)
    print("build_threads — 构建 xhs_comment_threads 聚合表")
    print("=" * 56)

    conn = get_conn()

    if rebuild:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE xhs_comment_threads")
        conn.commit()
        print("[rebuild] 已清空 xhs_comment_threads")

    # ── 1. 拉取所有评论
    print("正在加载 xhs_comments ...")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT comment_id, parent_comment_id, comment_level, content, "
            "note_id, note_title, user_id, nickname, create_time, ip_location, "
            "label_id, label_name "
            "FROM xhs_comments WHERE comment_id IS NOT NULL"
        )
        all_rows = cur.fetchall()
    print(f"  共 {len(all_rows)} 条评论")

    # ── 2. 拉取笔记发布时间（xhs_notes.time 是毫秒时间戳）
    print("正在加载 xhs_notes ...")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT note_id, title, publish_time "
            "FROM xhs_notes WHERE note_id IS NOT NULL"
        )
        note_rows = cur.fetchall()
    note_map = {r["note_id"]: r for r in note_rows}
    print(f"  共 {len(note_map)} 篇笔记")

    # ── 3. 建内存索引
    all_comments = {r["comment_id"]: r for r in all_rows}
    children_map: dict[str, list] = {}
    for row in all_rows:
        pid = row["parent_comment_id"]
        if pid:
            children_map.setdefault(pid, []).append(row)

    # 子评论按 create_time 排序（保持时间顺序）
    for pid in children_map:
        children_map[pid].sort(key=lambda x: x["create_time"] or "")

    # ── 4. 找出一级评论
    level1 = [r for r in all_rows if r["comment_level"] == 1]
    print(f"  一级评论: {len(level1)} 条")

    # ── 5. 构建并批量写入
    BATCH = 500
    inserted = 0
    skipped = 0

    for i in range(0, len(level1), BATCH):
        batch = level1[i:i + BATCH]
        records = []
        for row in batch:
            cid = row["comment_id"]
            note_info = note_map.get(row["note_id"] or "", {})

            child_lines = build_thread_text(cid, children_map, all_comments)
            thread_text = "\n".join(child_lines) if child_lines else None

            records.append({
                "comment_id":       cid,
                "content":          (row["content"] or "")[:1024],
                "thread_text":      thread_text,
                "note_id":          row["note_id"],
                "note_title":       (note_info.get("title") or row.get("note_title") or "")[:512],
                "note_publish_time": note_info.get("publish_time"),
                "user_id":          row["user_id"],
                "nickname":         (row["nickname"] or "")[:128],
                "create_time":      row["create_time"],
                "ip_location":      (row["ip_location"] or "")[:64],
                "label_id":         row["label_id"],
                "label_name":       (row["label_name"] or "")[:16],
            })

        with conn.cursor() as cur:
            sql = (
                "INSERT IGNORE INTO xhs_comment_threads "
                "(comment_id, content, thread_text, note_id, note_title, note_publish_time, "
                "user_id, nickname, create_time, ip_location, label_id, label_name) "
                "VALUES (%(comment_id)s, %(content)s, %(thread_text)s, %(note_id)s, "
                "%(note_title)s, %(note_publish_time)s, %(user_id)s, %(nickname)s, "
                "%(create_time)s, %(ip_location)s, %(label_id)s, %(label_name)s)"
            )
            cur.executemany(sql, records)
            inserted += cur.rowcount
            skipped += len(records) - cur.rowcount
        conn.commit()

        done = min(i + BATCH, len(level1))
        print(f"  进度: {done}/{len(level1)} ({done*100//len(level1)}%)  写入={inserted}  跳过={skipped}", end="\r")

    print()
    conn.close()

    print("\n" + "=" * 56)
    print(f"完成！写入: {inserted} 条  跳过(已存在): {skipped} 条")
    print("=" * 56)


if __name__ == "__main__":
    main()
