#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/filter_valuable.py
两步筛选 xhs_comment_threads 中的有价值一级评论：
  1. 填充 reply_count（直接子评论数）
  2. 在 label_id IN (1-6) 中取 reply_count 降序前 N 条，标记 is_valuable=1

用法：
  python tools/filter_valuable.py              # 正式写库
  python tools/filter_valuable.py --dry-run    # 只预览，不写库
  python tools/filter_valuable.py --rebuild    # 重置后重跑
  python tools/filter_valuable.py --top 4000   # 调整保留数量（默认4000）
"""

import io
import os
import sys
import argparse
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

VALUABLE_LABELS = (1, 2, 3, 4, 5, 6)


def get_conn():
    return pymysql.connect(**_DB)


def fill_reply_count(conn, dry_run: bool):
    """用 xhs_comments 表的直接子评论数填充 reply_count。"""
    print("正在统计直接子评论数 ...")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT parent_comment_id, COUNT(*) AS cnt "
            "FROM xhs_comments "
            "WHERE comment_level > 1 AND parent_comment_id IS NOT NULL "
            "GROUP BY parent_comment_id"
        )
        rows = cur.fetchall()
    print(f"  找到 {len(rows)} 个有子评论的一级评论")

    if dry_run:
        sample = rows[:5]
        for r in sample:
            print(f"    comment_id={r['parent_comment_id']}  children={r['cnt']}")
        print("  [dry-run] 跳过写库")
        return

    # 批量更新
    BATCH = 500
    updated = 0
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        cases = " ".join(f"WHEN %s THEN %s" for _ in batch)
        ids = [r["parent_comment_id"] for r in batch]
        params = []
        for r in batch:
            params.extend([r["parent_comment_id"], r["cnt"]])
        params.extend(ids)
        sql = (
            f"UPDATE xhs_comment_threads "
            f"SET reply_count = CASE comment_id {cases} END "
            f"WHERE comment_id IN ({','.join(['%s'] * len(ids))})"
        )
        with conn.cursor() as cur:
            cur.execute(sql, params)
            updated += cur.rowcount
        conn.commit()
        done = min(i + BATCH, len(rows))
        print(f"  reply_count 写入进度: {done}/{len(rows)}", end="\r")

    print(f"\n  reply_count 更新完成，共更新 {updated} 行")


def preview_distribution(conn, top_n: int):
    """预览 label 1-6 中 reply_count 的分布以及筛选阈值。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT label_id, label_name, COUNT(*) AS cnt, "
            "MAX(reply_count) AS max_rc, MIN(reply_count) AS min_rc, "
            "ROUND(AVG(reply_count), 1) AS avg_rc "
            "FROM xhs_comment_threads "
            "WHERE label_id IN (1,2,3,4,5,6) "
            "GROUP BY label_id, label_name ORDER BY label_id"
        )
        rows = cur.fetchall()

    print("\n─── label 1-6 reply_count 分布 ───")
    total = 0
    for r in rows:
        print(
            f"  label {r['label_id']} {r['label_name']:8s}  "
            f"cnt={r['cnt']:5d}  max={r['max_rc']}  avg={r['avg_rc']}"
        )
        total += r["cnt"]
    print(f"  合计: {total} 条")

    # 找出 top_n 的 reply_count 阈值
    with conn.cursor() as cur:
        cur.execute(
            "SELECT reply_count FROM xhs_comment_threads "
            "WHERE label_id IN (1,2,3,4,5,6) "
            "ORDER BY reply_count DESC "
            f"LIMIT {top_n}, 1"
        )
        row = cur.fetchone()
    threshold = row["reply_count"] if row else 0
    print(f"\n  取前 {top_n} 条的 reply_count 阈值约为: {threshold}")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM xhs_comment_threads "
            "WHERE label_id IN (1,2,3,4,5,6) "
            f"AND reply_count >= {threshold}"
        )
        cnt = cur.fetchone()["cnt"]
    print(f"  reply_count >= {threshold} 的记录数: {cnt}")


def mark_valuable(conn, top_n: int, dry_run: bool, rebuild: bool):
    """标记 is_valuable。"""
    if rebuild and not dry_run:
        with conn.cursor() as cur:
            cur.execute("UPDATE xhs_comment_threads SET is_valuable = NULL, "
                        "l1_tag_id=NULL, l1_tag_name=NULL, l2_tag_id=NULL, "
                        "l2_tag_name=NULL, l3_tag_name=NULL")
        conn.commit()
        print("[rebuild] 已重置 is_valuable 及三级标签列")

    # 先把 label 1-6 全部置 0（过滤掉 reply_count 较低的部分）
    # 然后把 top_n 置 1
    if dry_run:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM xhs_comment_threads "
                f"WHERE label_id IN (1,2,3,4,5,6)"
            )
            total_valid = cur.fetchone()["cnt"]
        print(f"\n[dry-run] label 1-6 共 {total_valid} 条，将标记前 {top_n} 条为 is_valuable=1")
        return

    print(f"\n正在标记 is_valuable ...")
    with conn.cursor() as cur:
        # 所有 label 1-6 先置 0
        cur.execute(
            "UPDATE xhs_comment_threads SET is_valuable = 0 "
            "WHERE label_id IN (1,2,3,4,5,6)"
        )
        conn.commit()
        print(f"  label 1-6 全部置 0，共 {cur.rowcount} 行")

        # 取 reply_count 降序前 top_n 置 1
        cur.execute(
            "UPDATE xhs_comment_threads t "
            "JOIN ( "
            "  SELECT comment_id FROM xhs_comment_threads "
            "  WHERE label_id IN (1,2,3,4,5,6) "
            "  ORDER BY reply_count DESC "
            f"  LIMIT {top_n} "
            ") top ON t.comment_id = top.comment_id "
            "SET t.is_valuable = 1"
        )
        conn.commit()
        marked = cur.rowcount
    print(f"  is_valuable=1 标记完成，共 {marked} 行")

    # 其余 label 7-10 及 NULL 置 0
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE xhs_comment_threads SET is_valuable = 0 "
            "WHERE label_id NOT IN (1,2,3,4,5,6) OR label_id IS NULL"
        )
        conn.commit()
        print(f"  label 7-10/NULL 置 0，共 {cur.rowcount} 行")


def show_result(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT label_id, label_name, is_valuable, COUNT(*) AS cnt "
            "FROM xhs_comment_threads "
            "WHERE is_valuable = 1 "
            "GROUP BY label_id, label_name, is_valuable ORDER BY label_id"
        )
        rows = cur.fetchall()
    print("\n─── is_valuable=1 分布 ───")
    total = 0
    for r in rows:
        print(f"  label {r['label_id']} {r['label_name']:8s}  cnt={r['cnt']}")
        total += r["cnt"]
    print(f"  合计: {total} 条")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--top", type=int, default=4000, help="保留的有价值评论数量（默认4000）")
    args = parser.parse_args()

    print("=" * 56)
    print("filter_valuable — 价值筛选 + reply_count 填充")
    print("=" * 56)
    if args.dry_run:
        print("[dry-run 模式] 只预览，不写库\n")

    conn = get_conn()

    fill_reply_count(conn, dry_run=args.dry_run)
    preview_distribution(conn, top_n=args.top)
    mark_valuable(conn, top_n=args.top, dry_run=args.dry_run, rebuild=args.rebuild)

    if not args.dry_run:
        show_result(conn)

    conn.close()
    print("\n" + "=" * 56)
    print("完成！")
    print("=" * 56)


if __name__ == "__main__":
    main()
