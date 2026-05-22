#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/tag_comments.py
用 GLM-4-Flash 批量给 ai_platform.xhs_comments 打10分类标签。

写入两列（已存在）：
  label_id   TINYINT — 1-10 分类编号
  label_name VARCHAR — 分类名称

增量运行：只处理 label_id IS NULL 的评论，重复执行安全。

用法：
  python tools/tag_comments.py                    # 处理全部未标注（10并发）
  python tools/tag_comments.py --limit 100        # 只处理前100条（测试）
  python tools/tag_comments.py --workers 5        # 指定并发数
  python tools/tag_comments.py --reset-all        # 清除全部label重新打
"""

import io
import json
import os
import re
import sys
import time
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

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

_GLM_API_KEY  = os.environ.get("GLM_API_KEY", "1ffaada346634edcb1a28b02dca2b048.Shaduw0bUq9NtqTc")
_GLM_MODEL    = "glm-4-flash"
_GLM_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

BATCH_SIZE  = 5
MAX_WORKERS = 10
MAX_RETRY   = 3
API_TIMEOUT = 90

LABEL_MAP = {
    1:  "产品痛点",
    2:  "选择障碍",
    3:  "竞品好评",
    4:  "价格与渠道",
    5:  "宝宝拒食",
    6:  "适应反馈",
    7:  "社交互动",
    8:  "无意义标记",
    9:  "广告引流",
    10: "无效表达",
}

# ─────────────────────────────────────────────
# 规则预分类（只拦最明确的两类，减少误杀）
# ─────────────────────────────────────────────

_AD_PATTERN = re.compile(r'私我|加[Vv我]|扫[我]?码|微信号|v信|[Ww][Xx]号|代购|拼单返现')
_NO_CJK = re.compile(r'[一-鿿㐀-䶿]')


def rule_label(content: str) -> int | None:
    """返回规则确定的 label_id，无法确定返回 None 交给 GLM。"""
    c = (content or "").strip()
    if not c:
        return 8
    if not _NO_CJK.search(c):
        return 8
    if _AD_PATTERN.search(c):
        return 9
    return None


# ─────────────────────────────────────────────
# 数据库工具
# ─────────────────────────────────────────────

def get_conn():
    return pymysql.connect(**_DB)


def apply_rules(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT comment_id, content FROM xhs_comments "
            "WHERE label_id IS NULL AND content IS NOT NULL"
        )
        rows = cur.fetchall()

    to_write = []
    for row in rows:
        lid = rule_label(row["content"])
        if lid is not None:
            to_write.append({"comment_id": row["comment_id"], "label_id": lid})

    if to_write:
        with conn.cursor() as cur:
            for item in to_write:
                lid = item["label_id"]
                cur.execute(
                    "UPDATE xhs_comments SET label_id=%s, label_name=%s WHERE comment_id=%s",
                    (lid, LABEL_MAP[lid], item["comment_id"]),
                )
        conn.commit()
    return len(to_write)


def fetch_all_untagged(conn, limit=None) -> list:
    sql = (
        "SELECT comment_id, content, like_count, note_title FROM xhs_comments "
        "WHERE label_id IS NULL AND content IS NOT NULL AND content != ''"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def write_batch(conn, results: list) -> int:
    if not results:
        return 0
    updated = 0
    with conn.cursor() as cur:
        for item in results:
            lid = item["label_id"]
            lname = LABEL_MAP.get(lid, "无效表达")
            cur.execute(
                "UPDATE xhs_comments SET label_id=%s, label_name=%s WHERE comment_id=%s",
                (lid, lname, item["comment_id"]),
            )
            updated += cur.rowcount
    conn.commit()
    return updated


def process_single_batch(batch: list) -> tuple:
    conn = get_conn()
    try:
        results, ok = tag_batch_with_retry(batch)
        if ok and results:
            written = write_batch(conn, results)
            return written, len(batch) - len(results)
        else:
            return 0, len(batch)
    finally:
        conn.close()


# ─────────────────────────────────────────────
# GLM API
# ─────────────────────────────────────────────

_SYSTEM_PROMPT = """你是评论分类专家，对小红书果泥/辅食相关评论做10分类标注。

【标签定义与边界】
1 产品痛点：对果泥/辅食产品/食材的明确负面体验，必须能看出具体"哪里不好"。
  ✓ "这个包装根本撕不开" "吃完拉肚子了" "蓝莓打成泥太酸了宝宝不接受"
  ✗ 仅"太酸了"（无具体产品上下文）→ 判8；"少给孩子吃水果"（建议）→ 判10

2 选择障碍：有明确疑问（含"？"或"求"）或表达担忧/困惑，暂时没找到满意方案。
  ✓ "担心有防腐剂" "4个月能吃吗" "不知道该不该吃了"
  ✗ 只是陈述操作步骤（先倒水再加米糊）→ 判10；纯打卡提问 → 判10

3 竞品好评：必须出现品牌名或具体产品型号，且是正面推荐。
  ✓ "小皮西梅泥便秘救星" "嘉宝米粉宝宝很爱吃"
  ✗ 没有品牌名只说"方便好用" → 判6或7；"必须照着做" → 判7

4 价格与渠道：只关心在哪买、多少钱、有没有优惠，未涉及产品体验。
  ✓ "求链接" "哪里买便宜" "等活动价"
  ✗ 顺带问了一句价格但主要在问产品 → 判2

5 宝宝拒食：描述宝宝"不吃/吐出/拒绝/哭闹"的喂养现象，核心词是"不吃"。
  ✓ "一喂就吐出来" "只肯吃甜的酸的不要"
  ✗ "宝宝在喊救命哈哈哈"（玩笑，无实际拒食描述）→ 判7

6 适应反馈：描述吃完后宝宝身体变化（便便/胀气/过敏/吐），中性观察。
  ✓ "火龙果吃多了串稀" "吃了胡萝卜泥粑粑变橙色"
  ✗ 操作建议/经验分享（先倒水再加米糊）→ 判10；宝宝直接拒食 → 判5

7 社交互动：与产品/辅食无关的聊天、祝福、夸颜值、互动打招呼。
  ✓ "宝贝好可爱" "祝宝宝早日康复" "哈哈哈哈好有趣"
  ✗ 虽然是情感表达但带了具体辅食问题 → 优先判2

8 无意义标记：无汉字或极短无信息量，纯感叹/表情/收藏动作。
  ✓ "码住" "😂😂" "哇" "收藏了"
  ✗ 虽然短但有实质内容（"太酸了宝宝不喜欢"）→ 判1或5

9 广告引流：有明显引流动作词（私我/加V/扫码/微信号），意图拉客。
  ✓ "要平替私我" "加V优惠" "我家有货扫码"
  ✗ 只是推荐产品没有引流词 → 判3

10 无效表达：以上都不符合，意图模糊或完全无法归类。

【判断顺序】
① 有引流动作词 → 9
② 有品牌名且夸 → 3；有品牌名且骂 → 1
③ 有"？"或"求"且表达担忧/困惑 → 2
④ 核心是"不吃/拒食/吐" → 5
⑤ 吃后身体变化 → 6
⑥ 明确产品负面体验 → 1
⑦ 问哪买/价格 → 4
⑧ 纯聊天/祝福/夸颜值/无关互动 → 7
⑨ 纯标记/感叹/无汉字 → 8
⑩ 其余 → 10"""

_USER_TEMPLATE = """对下列评论逐条分类，只输出JSON数组，每个元素含idx(输入序号)和label(1-10整数)，不要任何其他文字：

{comments_block}

输出示例：[{{"idx":1,"label":7}},{{"idx":2,"label":2}}]"""


def _build_prompt(batch: list) -> str:
    lines = []
    for i, row in enumerate(batch, 1):
        content = str(row["content"]).replace("\n", " ").replace("\r", " ")[:200]
        like = int(row.get("like_count") or 0)
        title = str(row.get("note_title") or "")[:20].replace("\n", " ")
        lines.append(f"{i}. [赞={like}|《{title}》] {content}")
    return _USER_TEMPLATE.format(comments_block="\n".join(lines))


def _call_glm(prompt: str) -> str:
    payload = json.dumps({
        "model": _GLM_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.01,
        "max_tokens": 512,
    }, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        _GLM_ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {_GLM_API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def _parse_response(text: str, batch: list) -> list:
    raw = text.strip()
    parsed = None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group())
            except json.JSONDecodeError:
                pass

    if not isinstance(parsed, list):
        return []

    results = []
    for item in parsed:
        try:
            idx = int(item.get("idx", 0)) - 1
            if idx < 0 or idx >= len(batch):
                continue
            label_id = max(1, min(10, int(item.get("label", 10))))
            results.append({
                "comment_id": batch[idx]["comment_id"],
                "label_id": label_id,
            })
        except (TypeError, ValueError, KeyError):
            continue
    return results


def tag_batch_with_retry(batch: list) -> tuple:
    for attempt in range(MAX_RETRY + 1):
        try:
            prompt = _build_prompt(batch)
            text = _call_glm(prompt)
            results = _parse_response(text, batch)
            if results:
                return results, True
            print(f"    [解析空] 重试({attempt+1}/{MAX_RETRY})")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            print(f"    [HTTP {e.code}] {body} 重试({attempt+1}/{MAX_RETRY})")
        except Exception as e:
            print(f"    [错误] {e!r} 重试({attempt+1}/{MAX_RETRY})")
        if attempt < MAX_RETRY:
            time.sleep(2 * (attempt + 1))
    return [], False


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────

def main():
    limit = None
    workers = MAX_WORKERS
    reset_all = False
    args = sys.argv[1:]
    for flag in ("--limit", "--workers"):
        if flag in args:
            i = args.index(flag)
            try:
                val = int(args[i + 1])
                if flag == "--limit":
                    limit = val
                else:
                    workers = max(1, val)
            except (IndexError, ValueError):
                print("用法: python tools/tag_comments.py [--limit N] [--workers N] [--reset-all]")
                sys.exit(1)
    if "--reset-all" in args:
        reset_all = True

    print("=" * 60)
    print("xhs_comments 10分类标签工具 — GLM-4-Flash")
    print("=" * 60)

    conn = get_conn()

    if reset_all:
        with conn.cursor() as cur:
            cur.execute("UPDATE xhs_comments SET label_id=NULL, label_name=NULL WHERE label_id IS NOT NULL")
            n = cur.rowcount
        conn.commit()
        print(f"[reset-all] 已清除全部 {n} 条标签")

    print("正在执行规则预分类...")
    n_rule = apply_rules(conn)
    print(f"[规则层] 已标记 {n_rule} 条（纯符号/明确引流）")

    print(f"\n正在加载剩余未标注评论...")
    all_rows = fetch_all_untagged(conn, limit)
    conn.close()

    to_process = len(all_rows)
    print(f"待 GLM 处理: {to_process} 条  批次大小: {BATCH_SIZE}  并发数: {workers}")

    if to_process == 0:
        print("所有评论已标注完成。")
        _print_dist()
        return

    all_batches = [all_rows[i:i+BATCH_SIZE] for i in range(0, to_process, BATCH_SIZE)]
    total_batches = len(all_batches)
    print(f"共 {total_batches} 批，开始并发处理...\n")

    total_written = 0
    total_missed  = 0
    processed     = 0
    lock          = threading.Lock()

    def _update(written, missed):
        nonlocal total_written, total_missed, processed
        with lock:
            total_written += written
            total_missed  += missed
            processed     += written + missed

    done_batches = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_single_batch, b): b for b in all_batches}
        for future in as_completed(futures):
            try:
                written, missed = future.result()
            except Exception as e:
                batch = futures[future]
                written, missed = 0, len(batch)
                print(f"\n  [异常] {e!r}")
            _update(written, missed)
            done_batches += 1
            pct = processed / to_process * 100
            print(f"  批次 {done_batches:>5}/{total_batches}  "
                  f"已处理 {processed}/{to_process} ({pct:.0f}%)  "
                  f"写入={total_written}  未写={total_missed}", end="\r")

    print()
    _print_dist()

    remaining = to_process - total_written
    if remaining > 0:
        print(f"\n  提示: 仍有 {remaining} 条未标注（API失败），重新运行本脚本可增量补跑。")


def _print_dist():
    c = get_conn()
    with c.cursor() as cur:
        cur.execute(
            "SELECT label_id, label_name, COUNT(*) AS cnt FROM xhs_comments "
            "WHERE label_id IS NOT NULL GROUP BY label_id, label_name ORDER BY label_id"
        )
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) AS cnt FROM xhs_comments WHERE label_id IS NULL")
        unlabeled = cur.fetchone()["cnt"]
    c.close()

    print("\n" + "=" * 60)
    print("标签分布：")
    total = sum(r["cnt"] for r in rows)
    for row in rows:
        bar = "█" * int(row["cnt"] / max(total, 1) * 30)
        print(f"  {row['label_id']:2d} {row['label_name']:8s} {row['cnt']:6d}  {bar}")
    print(f"  未标注: {unlabeled}")
    print("=" * 60)


if __name__ == "__main__":
    main()
