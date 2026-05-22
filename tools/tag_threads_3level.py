#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/tag_threads_3level.py
对 xhs_comment_threads 中 is_valuable=1 的记录打三级标签（两步法）：
  Step-1：GLM 根据评论全文选出 l1（场景）+ l2（痛点/需求类型）
  Step-2：GLM 在 l2 候选词表中选 l3_tag_name（具体触发，半封闭）

只处理 is_valuable=1 且 l1_tag_id IS NULL 的记录（增量可重跑）。

用法：
  python tools/tag_threads_3level.py              # 正式打标
  python tools/tag_threads_3level.py --workers 5  # 调整并发数
  python tools/tag_threads_3level.py --rebuild     # 重置后重跑
"""

import io
import os
import sys
import re
import json
import time
import argparse
import urllib.request
import urllib.error
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

GLM_API_KEY  = os.environ.get("GLM_API_KEY", "1ffaada346634edcb1a28b02dca2b048.Shaduw0bUq9NtqTc")
GLM_MODEL    = "glm-4-flash"
GLM_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
API_TIMEOUT  = 90
BATCH_SIZE   = 3
MAX_TEXT_LEN = 2000

# ─── 新三级标签体系（喂养生命周期框架）──────────────────────────

L1_LABELS = [
    (1, "启动添加", "关于何时开始、如何排敏、初次尝试辅食"),
    (2, "日常喂养", "量/频率/搭配/拒食/挑食等日常执行问题"),
    (3, "身体反应", "吃后宝宝的生理或行为变化观察"),
    (4, "产品选择", "买哪个、哪里买、多少钱、适合几个月"),
    (5, "制作储存", "自制方法、加热方式、保存、食材搭配"),
]

L2_LABELS = [
    # L1=1 启动添加
    (101, 1, "开始时机",   ["几个月开始", "太早还是太晚", "医生建议月龄", "发育信号判断"]),
    (102, 1, "排敏方法",   ["单一食材排敏", "排敏天数", "过敏反应识别", "排敏顺序"]),
    (103, 1, "初次量与接受", ["第一口量", "宝宝吐出来", "不张嘴", "接受了很开心"]),
    # L1=2 日常喂养
    (201, 2, "拒食挑食",   ["只吃某一种", "闭嘴不张口", "吃几口就不吃了", "用舌头顶出来", "边吃边玩不专心"]),
    (202, 2, "喂养量困惑", ["每次吃多少克", "一天几顿", "加量节奏", "吃不完剩下怎么办"]),
    (203, 2, "搭配与进阶", ["混合几种食材", "从泥到颗粒过渡", "添加调味时机", "蛋白质搭配"]),
    (204, 2, "喂养工具方式", ["用勺子还是吸管杯", "喂养姿势", "自主进食训练", "辅食机使用"]),
    # L1=3 身体反应
    (301, 3, "消化问题",   ["便秘", "腹泻", "胀气放屁多", "大便颜色变化", "消化不良"]),
    (302, 3, "过敏反应",   ["脸起红疹", "嘴角红点", "荨麻疹", "眼睛红肿", "湿疹加重"]),
    (303, 3, "正向反应",   ["吃得很香", "抢着要", "便便正常", "体重增长好"]),
    (304, 3, "其他身体变化", ["睡眠变差", "出汗多", "口水增多", "发烧后食欲变化"]),
    # L1=4 产品选择
    (401, 4, "品牌对比",   ["哪个牌子好", "国产vs进口", "小皮vs嘉宝", "看成分对比"]),
    (402, 4, "成分顾虑",   ["有没有添加糖", "防腐剂", "添加剂", "配料表怎么看"]),
    (403, 4, "月龄适配",   ["几个月吃哪款", "段位选择", "升段时机"]),
    (404, 4, "价格渠道",   ["哪里买更便宜", "拼多多vs京东", "活动囤货", "性价比"]),
    (405, 4, "口味口感选择", ["宝宝喜欢什么口味", "甜的还是咸的", "质地稀稠"]),
    # L1=5 制作储存
    (501, 5, "自制方法",   ["蒸多久", "压泥技巧", "用辅食机还是料理棒", "加水量"]),
    (502, 5, "食材搭配",   ["荤素搭配", "补铁食材", "蔬菜种类", "水果加不加热"]),
    (503, 5, "加热保存",   ["冷藏几天", "冷冻保存", "解冻方式", "热多久"]),
    (504, 5, "食材采购",   ["用冷冻食材还是新鲜", "有机vs普通", "超市还是线上"]),
]

L1_MAP = {lid: name for lid, name, _ in L1_LABELS}
# l2_id -> (name, parent_l1_id, candidates)
L2_MAP = {lid: (name, parent, cands) for lid, parent, name, cands in L2_LABELS}

_L1_LIST = "\n".join(f"  {lid} {name}：{desc}" for lid, name, desc in L1_LABELS)
_L2_LIST = "\n".join(
    f"  {lid}（L1={parent}）{name}" for lid, parent, name, _ in L2_LABELS
)


def _build_step1_system():
    return f"""你是一个婴幼儿辅食评论分析专家。
请根据评论内容，从以下5个一级标签（场景）中选1个最匹配的，再从对应的二级标签中选1个最匹配的。

【一级标签（场景）】
{_L1_LIST}

【二级标签】
{_L2_LIST}

输出格式（严格JSON数组，每条评论一个对象）：
[{{"l1_tag_id": <数字>, "l1_tag_name": "<名称>", "l2_tag_id": <数字>, "l2_tag_name": "<名称>"}}, ...]

规则：
- l2_tag_id 必须属于所选 l1_tag_id 下的二级标签
- 数组长度必须等于输入评论数量
- 只输出JSON数组，不输出任何解释
"""

STEP1_SYSTEM = _build_step1_system()


def _build_step2_system(l2_id: int) -> str:
    info = L2_MAP.get(l2_id)
    if info:
        name, _, cands = info
        cands_str = "、".join(f'"{c}"' for c in cands)
        return f"""你是一个婴幼儿辅食评论分析专家。
二级标签为【{name}】，请从以下候选词中选出最贴切的一个作为三级标签：
候选词：{cands_str}

如果候选词都不合适，可以自填一个≤10字的短语。

输出格式（严格JSON数组）：
[{{"l3_tag_name": "<选中或自填的短语>"}}, ...]

规则：
- 数组长度必须等于输入评论数量
- 只输出JSON数组，不输出其他内容
"""
    return """请为每条评论生成一个≤10字的三级标签短语。
输出格式（严格JSON数组）：[{"l3_tag_name": "<短语>"}, ...]"""


_JSON_ARR_RE = re.compile(r'\[.*?\]', re.DOTALL)
_JSON_OBJ_RE = re.compile(r'\{[^{}]+\}', re.DOTALL)


def glm_call(system: str, user: str, max_tokens: int = 512) -> str:
    payload = json.dumps({
        "model": GLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "temperature": 0.01,
        "max_tokens": max_tokens,
    }, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        GLM_ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {GLM_API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def parse_array(raw: str, expected_len: int) -> list:
    raw = raw.strip()
    parsed = None
    m = _JSON_ARR_RE.search(raw)
    if m:
        try:
            parsed = json.loads(m.group())
        except Exception:
            pass
    if not isinstance(parsed, list):
        objs = []
        for mo in _JSON_OBJ_RE.finditer(raw):
            try:
                objs.append(json.loads(mo.group()))
            except Exception:
                pass
        parsed = objs if objs else []
    while len(parsed) < expected_len:
        parsed.append({})
    return parsed[:expected_len]


def build_text(row: dict) -> str:
    content = (row.get("content") or "").strip()
    thread  = (row.get("thread_text") or "").strip()
    combined = content + ("\n---回复---\n" + thread if thread else "")
    return combined[:MAX_TEXT_LEN]


def process_batch(batch: list[dict]) -> list[dict]:
    texts = [build_text(r) for r in batch]
    n = len(batch)

    # Step-1: l1 + l2
    numbered = "\n\n".join(f"【评论{i+1}】\n{t}" for i, t in enumerate(texts))
    user1 = f"请对以下{n}条评论分别打标签，输出长度为{n}的JSON数组：\n\n{numbered}"
    try:
        raw1  = glm_call(STEP1_SYSTEM, user1, max_tokens=n * 60 + 64)
        step1 = parse_array(raw1, n)
    except Exception:
        step1 = [{}] * n

    # Step-2: l3（按批次中最多的 l2 分组调用，简化为每批一次调用）
    # 用 step1 结果中出现最多的 l2_id 决定候选词表
    l2_ids = [s.get("l2_tag_id") for s in step1]
    dominant_l2 = max(set(l2_ids), key=l2_ids.count) if any(l2_ids) else None
    step2_sys = _build_step2_system(dominant_l2)
    parts = []
    for i, t in enumerate(texts):
        l2_name = (step1[i].get("l2_tag_name") or "")
        parts.append(f"【评论{i+1}】二级标签：{l2_name}\n{t[:400]}")
    user2 = f"请对以下{n}条评论各生成三级标签，输出长度为{n}的JSON数组：\n\n" + "\n\n".join(parts)
    try:
        raw2  = glm_call(step2_sys, user2, max_tokens=n * 20 + 32)
        step2 = parse_array(raw2, n)
    except Exception:
        step2 = [{}] * n

    VALID_L1 = {lid for lid, _, _ in L1_LABELS}
    VALID_L2 = set(L2_MAP.keys())

    outputs = []
    for row, s1, s2 in zip(batch, step1, step2):
        l1_id = s1.get("l1_tag_id")
        l2_id = s1.get("l2_tag_id")
        # 如果 l1_id 不合法但 l2_id 合法，从 l2 反推 l1
        if l1_id not in VALID_L1:
            if l2_id in VALID_L2:
                l1_id = L2_MAP[l2_id][1]  # parent l1
            else:
                l1_id = None
        # 校验 l2 合法且归属 l1
        if l2_id not in VALID_L2:
            l2_id = None
        if l2_id and l1_id:
            if L2_MAP.get(l2_id, (None, None, None))[1] != l1_id:
                l2_id = None
        l1_name = s1.get("l1_tag_name") or L1_MAP.get(l1_id)
        l2_name = s1.get("l2_tag_name") or (L2_MAP.get(l2_id, (None,))[0] if l2_id else None)
        l3_name = (s2.get("l3_tag_name") or "")[:64] or None
        outputs.append({
            "comment_id":  row["comment_id"],
            "l1_tag_id":   l1_id,
            "l1_tag_name": l1_name,
            "l2_tag_id":   l2_id,
            "l2_tag_name": l2_name,
            "l3_tag_name": l3_name,
        })
    return outputs


def write_results(conn, results: list[dict]):
    sql = (
        "UPDATE xhs_comment_threads SET "
        "l1_tag_id=%(l1_tag_id)s, l1_tag_name=%(l1_tag_name)s, "
        "l2_tag_id=%(l2_tag_id)s, l2_tag_name=%(l2_tag_name)s, "
        "l3_tag_name=%(l3_tag_name)s "
        "WHERE comment_id=%(comment_id)s"
    )
    with conn.cursor() as cur:
        cur.executemany(sql, results)
    conn.commit()


def get_conn():
    return pymysql.connect(**_DB)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    print("=" * 56)
    print("tag_threads_3level — 三级标签打标（喂养生命周期框架）")
    print("=" * 56)

    conn = get_conn()

    if args.rebuild:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE xhs_comment_threads SET "
                "l1_tag_id=NULL, l1_tag_name=NULL, "
                "l2_tag_id=NULL, l2_tag_name=NULL, l3_tag_name=NULL "
                "WHERE is_valuable=1"
            )
        conn.commit()
        print("[rebuild] 已重置 is_valuable=1 的三级标签\n")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT comment_id, content, thread_text "
            "FROM xhs_comment_threads "
            "WHERE is_valuable=1 AND l1_tag_id IS NULL"
        )
        rows = cur.fetchall()
    conn.close()

    total = len(rows)
    print(f"待处理: {total} 条  batch={BATCH_SIZE}  workers={args.workers}\n")
    if total == 0:
        print("无待处理记录。")
        return

    batches = [rows[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    done = 0
    failed = 0

    def run_batch(b):
        result = process_batch(b)
        c = get_conn()
        try:
            write_results(c, result)
        finally:
            c.close()
        return len(result)

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(run_batch, b): b for b in batches}
        for fut in as_completed(futures):
            try:
                n = fut.result()
                done += n
            except Exception as e:
                failed += len(futures[fut])
                print(f"\n  [error] {e}")
            pct = done * 100 // total if total else 100
            print(f"  进度: {done}/{total} ({pct}%)  失败={failed}", end="\r")
            time.sleep(0.02)

    print(f"\n\n{'='*56}")
    print(f"完成！处理={done}  失败={failed}")
    print(f"{'='*56}")


if __name__ == "__main__":
    main()
