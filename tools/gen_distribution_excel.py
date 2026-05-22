#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成评论数据分布分析 Excel
输出路径：E:/work/小红书爬虫/评论分布分析.xlsx
"""

import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pymysql
import pymysql.cursors
import openpyxl
from openpyxl.styles import (
    PatternFill, Font, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter

_DB = dict(
    host="120.24.236.119", port=3306,
    user="ai_admin", password="AiAdmin@2026#123",
    database="ai_platform", charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor, connect_timeout=10,
)

# ── 颜色主题 ──
L1_COLORS = {
    1: "4472C4",  # 蓝
    2: "ED7D31",  # 橙
    3: "A9D18E",  # 绿
    4: "9E3F8F",  # 紫
    5: "F4B942",  # 金
}
HEADER_FILL  = PatternFill("solid", fgColor="2E4057")
HEADER_FONT  = Font(bold=True, color="FFFFFF", size=10)
SUBHD_FILL   = PatternFill("solid", fgColor="D9E2F3")
SUBHD_FONT   = Font(bold=True, size=10)
THIN = Side(style="thin", color="CCCCCC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

def hdr_fill(hex6): return PatternFill("solid", fgColor=hex6)
def row_fill(hex6):
    r,g,b = int(hex6[0:2],16), int(hex6[2:4],16), int(hex6[4:6],16)
    r2,g2,b2 = min(255,r+80), min(255,g+80), min(255,b+80)
    return PatternFill("solid", fgColor=f"{r2:02X}{g2:02X}{b2:02X}")

def style_cell(cell, fill=None, font=None, align=None, border=True):
    if fill:   cell.fill   = fill
    if font:   cell.font   = font
    if align:  cell.alignment = align
    if border: cell.border = BORDER

def auto_width(ws, min_w=8, max_w=40):
    for col in ws.columns:
        length = max(
            len(str(c.value or "")) for c in col
        )
        ws.column_dimensions[get_column_letter(col[0].column)].width = \
            min(max_w, max(min_w, length + 2))

def write_headers(ws, headers, row=1, fill=HEADER_FILL, font=HEADER_FONT):
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=c, value=h)
        style_cell(cell, fill=fill, font=font,
                   align=Alignment(horizontal="center", vertical="center", wrap_text=True))

CENTER = Alignment(horizontal="center", vertical="center")
LEFT   = Alignment(horizontal="left",   vertical="center", wrap_text=True)

def pct(part, total):
    return f"{part/total*100:.1f}%" if total else "-"

# ─────────────────────────────────────────────────────────────────────────────
def main():
    conn = pymysql.connect(**_DB)

    # ── 查数据 ──
    def q(sql):
        with conn.cursor() as c: c.execute(sql); return c.fetchall()

    total_comments = q("SELECT COUNT(*) AS n FROM xhs_comments")[0]["n"]
    l1_count       = q("SELECT COUNT(*) AS n FROM xhs_comments WHERE comment_level=1")[0]["n"]
    valuable_count = q("SELECT COUNT(*) AS n FROM xhs_comment_threads WHERE is_valuable=1")[0]["n"]
    not_val_count  = q("SELECT COUNT(*) AS n FROM xhs_comment_threads WHERE is_valuable=0")[0]["n"]

    # L1 汇总（以 l1_tag_id 为主键聚合）
    l1_rows = q("""
        SELECT l1_tag_id,
               CASE l1_tag_id
                 WHEN 1 THEN '启动添加'
                 WHEN 2 THEN '日常喂养'
                 WHEN 3 THEN '身体反应'
                 WHEN 4 THEN '产品选择'
                 WHEN 5 THEN '制作储存'
               END AS l1_name,
               COUNT(*) AS cnt
        FROM xhs_comment_threads WHERE is_valuable=1
        GROUP BY l1_tag_id
        ORDER BY l1_tag_id
    """)

    # L2 汇总
    l2_rows = q("""
        SELECT l1_tag_id,
               CASE l1_tag_id
                 WHEN 1 THEN '启动添加'
                 WHEN 2 THEN '日常喂养'
                 WHEN 3 THEN '身体反应'
                 WHEN 4 THEN '产品选择'
                 WHEN 5 THEN '制作储存'
               END AS l1_name,
               l2_tag_id, l2_tag_name, COUNT(*) AS cnt
        FROM xhs_comment_threads WHERE is_valuable=1
        GROUP BY l1_tag_id, l2_tag_id, l2_tag_name
        ORDER BY l1_tag_id, cnt DESC
    """)

    # L3 Top 热词
    l3_rows = q("""
        SELECT l1_tag_id,
               CASE l1_tag_id
                 WHEN 1 THEN '启动添加'
                 WHEN 2 THEN '日常喂养'
                 WHEN 3 THEN '身体反应'
                 WHEN 4 THEN '产品选择'
                 WHEN 5 THEN '制作储存'
               END AS l1_name,
               l2_tag_name, l3_tag_name, COUNT(*) AS cnt
        FROM xhs_comment_threads WHERE is_valuable=1 AND l3_tag_name IS NOT NULL
        GROUP BY l1_tag_id, l2_tag_name, l3_tag_name
        ORDER BY cnt DESC
        LIMIT 80
    """)

    # 无价值评论分布
    noval_rows = q("""
        SELECT label_id, label_name, COUNT(*) AS cnt
        FROM xhs_comment_threads
        WHERE is_valuable=0 OR is_valuable IS NULL
        GROUP BY label_id, label_name
        ORDER BY label_id
    """)

    # 各 L1 示例评论（每个取 reply_count 最高的5条）
    ex_rows = q("""
        SELECT t.l1_tag_id,
               CASE t.l1_tag_id
                 WHEN 1 THEN '启动添加'
                 WHEN 2 THEN '日常喂养'
                 WHEN 3 THEN '身体反应'
                 WHEN 4 THEN '产品选择'
                 WHEN 5 THEN '制作储存'
               END AS l1_name,
               t.l2_tag_name, t.l3_tag_name,
               t.content, t.reply_count
        FROM xhs_comment_threads t
        INNER JOIN (
            SELECT l1_tag_id, comment_id,
                   ROW_NUMBER() OVER (PARTITION BY l1_tag_id ORDER BY reply_count DESC) AS rn
            FROM xhs_comment_threads WHERE is_valuable=1
        ) r ON t.comment_id=r.comment_id AND r.rn<=5
        ORDER BY t.l1_tag_id, t.reply_count DESC
    """)

    conn.close()

    # ─────────────────────────────────────────────────────────────────────────
    wb = openpyxl.Workbook()

    # ══════════════════════════════════════════════════════════════════
    # Sheet 1：概览
    # ══════════════════════════════════════════════════════════════════
    ws1 = wb.active
    ws1.title = "概览"

    ws1.merge_cells("A1:D1")
    t = ws1["A1"]
    t.value = "小红书辅食评论数据概览"
    t.font  = Font(bold=True, size=14, color="2E4057")
    t.alignment = CENTER
    ws1.row_dimensions[1].height = 30

    headers1 = ["指标", "数量（条）", "占比", "说明"]
    write_headers(ws1, headers1, row=2)

    overview = [
        ("全量评论（xhs_comments）", total_comments, "100%",
         "xhs_comments 表全量，含各层级评论"),
        ("一级评论", l1_count, pct(l1_count, total_comments),
         "comment_level=1 的根评论，也是分析单元"),
        ("有价值评论（is_valuable=1）", valuable_count, pct(valuable_count, l1_count),
         "label 1-6 且 reply_count 排名前 4000，已完成三级打标"),
        ("无价值评论（is_valuable=0）", not_val_count, pct(not_val_count, l1_count),
         "label 7-10 / 未标 / label 1-6 中讨论度较低的评论"),
    ]
    fills_ov = [
        PatternFill("solid", fgColor="EBF3FB"),
        PatternFill("solid", fgColor="D6EAF8"),
        PatternFill("solid", fgColor="AED6F1"),
        PatternFill("solid", fgColor="F8F9FA"),
    ]
    for i, (label, cnt, pct_s, desc) in enumerate(overview, 3):
        vals = [label, cnt, pct_s, desc]
        for j, v in enumerate(vals, 1):
            cell = ws1.cell(row=i, column=j, value=v)
            cell.fill   = fills_ov[i-3]
            cell.border = BORDER
            cell.alignment = CENTER if j in (2,3) else LEFT
            if j == 2:
                cell.number_format = "#,##0"

    # 有价值 vs 无价值定义说明框
    ws1.merge_cells("A8:D8")
    t = ws1["A8"]
    t.value = "「有价值」定义"
    t.font  = Font(bold=True, size=11, color="2E4057")
    t.alignment = LEFT

    definitions = [
        ("筛选条件 1", "原始标签（label_id）属于 1-6",
         "对应：产品痛点、选择障碍、竞品好评、价格与渠道、宝宝拒食、适应反馈"),
        ("筛选条件 2", "reply_count（直接子评论数）排名前 4,000",
         "回复越多说明话题讨论热度越高，信息密度越大"),
        ("排除范围",   "label 7-10：社交互动、无意义标记、广告引流、无效表达",
         "这类评论缺乏实质信息，无法用于痛点挖掘和场景分析"),
    ]
    write_headers(ws1, ["", "筛选条件", "筛选逻辑", "排除原因"], row=9,
                  fill=SUBHD_FILL, font=SUBHD_FONT)
    for i, (label, cond, reason) in enumerate(definitions, 10):
        for j, v in enumerate([label, cond, reason], 2):
            cell = ws1.cell(row=i, column=j, value=v)
            cell.border = BORDER
            cell.alignment = LEFT

    auto_width(ws1)
    ws1.column_dimensions["A"].width = 28
    ws1.column_dimensions["B"].width = 16
    ws1.column_dimensions["C"].width = 14
    ws1.column_dimensions["D"].width = 45

    # ══════════════════════════════════════════════════════════════════
    # Sheet 2：L1 分布
    # ══════════════════════════════════════════════════════════════════
    ws2 = wb.create_sheet("一级标签分布")

    ws2.merge_cells("A1:E1")
    t = ws2["A1"]
    t.value = "有价值评论 · 一级标签（L1）分布"
    t.font  = Font(bold=True, size=13, color="2E4057")
    t.alignment = CENTER
    ws2.row_dimensions[1].height = 28

    write_headers(ws2, ["L1 ID", "一级标签", "数量", "占比", "标签含义"], row=2)

    l1_desc = {
        1: "辅食添加启动期：何时开始、如何引入、初次量与接受度、排敏流程",
        2: "日常喂养运营期：喂养量、频率、拒食/挑食、搭配进阶、工具方式",
        3: "宝宝身体反应：消化问题、过敏反应、正向体验、其他身体变化",
        4: "产品选择决策：品牌/月龄适配、价格渠道、成分顾虑、口味选择",
        5: "食物制作与储存：自制方法、食材搭配、加热保存、采购渠道",
    }
    # 按 l1_tag_id 聚合
    l1_agg = {}
    for r in l1_rows:
        lid = r["l1_tag_id"]
        if lid not in l1_agg:
            l1_agg[lid] = 0
        l1_agg[lid] += r["cnt"]

    for i, (lid, cnt) in enumerate(sorted(l1_agg.items()), 3):
        color = L1_COLORS.get(lid, "CCCCCC")
        fill  = hdr_fill(color)
        row_f = row_fill(color)
        vals  = [lid, ["启动添加","日常喂养","身体反应","产品选择","制作储存"][lid-1],
                 cnt, pct(cnt, valuable_count), l1_desc.get(lid, "")]
        for j, v in enumerate(vals, 1):
            cell = ws2.cell(row=i, column=j, value=v)
            cell.fill   = fill if j <= 2 else row_f
            cell.border = BORDER
            cell.alignment = CENTER if j in (1,3,4) else LEFT
            if j == 3:
                cell.number_format = "#,##0"
            if j in (1,2):
                cell.font = Font(bold=True, color="FFFFFF")

    auto_width(ws2)
    ws2.column_dimensions["E"].width = 55

    # ══════════════════════════════════════════════════════════════════
    # Sheet 3：L2 分布
    # ══════════════════════════════════════════════════════════════════
    ws3 = wb.create_sheet("二级标签分布")

    ws3.merge_cells("A1:F1")
    t = ws3["A1"]
    t.value = "有价值评论 · 二级标签（L2）分布"
    t.font  = Font(bold=True, size=13, color="2E4057")
    t.alignment = CENTER
    ws3.row_dimensions[1].height = 28

    write_headers(ws3, ["L1 ID", "一级标签", "L2 ID", "二级标签", "数量", "占L1%"], row=2)

    # 聚合 L2（以 l2_tag_id 为主键；null L2 归入"其他"）
    l2_agg = {}  # (l1_id, l2_id, l2_name) -> cnt
    for r in l2_rows:
        key = (r["l1_tag_id"], r["l2_tag_id"], r["l2_tag_name"])
        l2_agg[key] = l2_agg.get(key, 0) + r["cnt"]

    # 计算每个 L1 总数
    l1_total = {k: v for k, v in l1_agg.items()}

    row_idx = 3
    prev_l1 = None
    for (l1_id, l2_id, l2_name), cnt in sorted(
        l2_agg.items(), key=lambda x: (x[0][0], -x[1])
    ):
        color = L1_COLORS.get(l1_id, "CCCCCC")
        fill  = hdr_fill(color)
        row_f = row_fill(color)

        l1_name = ["启动添加","日常喂养","身体反应","产品选择","制作储存"][l1_id-1]
        vals = [l1_id, l1_name,
                l2_id or "-",
                l2_name or "其他/混合",
                cnt,
                pct(cnt, l1_total.get(l1_id, 1))]

        for j, v in enumerate(vals, 1):
            cell = ws3.cell(row=row_idx, column=j, value=v)
            if j <= 2:
                cell.fill = fill
                cell.font = Font(bold=(prev_l1 != l1_id), color="FFFFFF")
            else:
                cell.fill = row_f
            cell.border = BORDER
            cell.alignment = CENTER if j in (1,3,5,6) else LEFT
            if j == 5:
                cell.number_format = "#,##0"

        prev_l1 = l1_id
        row_idx += 1

    auto_width(ws3)

    # ══════════════════════════════════════════════════════════════════
    # Sheet 4：L3 热词 Top 80
    # ══════════════════════════════════════════════════════════════════
    ws4 = wb.create_sheet("三级标签热词")

    ws4.merge_cells("A1:F1")
    t = ws4["A1"]
    t.value = "有价值评论 · 三级标签（L3）热词 TOP 80"
    t.font  = Font(bold=True, size=13, color="2E4057")
    t.alignment = CENTER
    ws4.row_dimensions[1].height = 28

    write_headers(ws4, ["排名", "一级标签", "二级标签", "三级标签（场景热词）", "数量", "说明"], row=2)

    l3_desc_hint = {
        "每次吃多少克": "最高频问题：家长对单次用量没有信心",
        "初次量与接受": "辅食引入第一口的量与宝宝接受情况",
        "哪里买更便宜": "价格敏感，关注购买渠道优惠",
        "冷藏几天": "家长最关心食品安全与储存时长",
        "月龄适配": "不同月龄对应哪款产品是核心决策焦点",
        "几个月吃哪款": "按月龄推荐产品的强需求",
        "排敏方法": "新食材引入时如何规避过敏风险",
        "宝宝喜欢什么口味": "购买前口味偏好咨询",
    }

    for rank, r in enumerate(l3_rows, 1):
        l1_id  = r["l1_tag_id"]
        color  = L1_COLORS.get(l1_id, "CCCCCC")
        row_f  = row_fill(color)
        desc   = l3_desc_hint.get(r["l3_tag_name"], "")
        vals   = [rank,
                  ["启动添加","日常喂养","身体反应","产品选择","制作储存"][l1_id-1],
                  r["l2_tag_name"] or "-",
                  r["l3_tag_name"] or "-",
                  r["cnt"],
                  desc]
        for j, v in enumerate(vals, 1):
            cell = ws4.cell(row=rank+2, column=j, value=v)
            cell.fill   = row_f
            cell.border = BORDER
            cell.alignment = CENTER if j in (1,5) else LEFT
            if j == 5:
                cell.number_format = "#,##0"

    auto_width(ws4)
    ws4.column_dimensions["D"].width = 22
    ws4.column_dimensions["F"].width = 35

    # ══════════════════════════════════════════════════════════════════
    # Sheet 5：无价值评论分布
    # ══════════════════════════════════════════════════════════════════
    ws5 = wb.create_sheet("无价值评论构成")

    ws5.merge_cells("A1:D1")
    t = ws5["A1"]
    t.value = "无价值评论（is_valuable=0）· 原始标签构成"
    t.font  = Font(bold=True, size=13, color="2E4057")
    t.alignment = CENTER
    ws5.row_dimensions[1].height = 28

    write_headers(ws5, ["原始标签ID", "原始标签名", "数量", "排除原因"], row=2)

    noval_desc = {
        None: "未打标（label_id IS NULL）",
        1:  "产品痛点：label 1-6 中 reply_count 较低，讨论度不足",
        2:  "选择障碍：同上，讨论度排名靠后",
        3:  "竞品好评：同上",
        4:  "价格与渠道：同上",
        5:  "宝宝拒食：同上",
        6:  "适应反馈：同上",
        7:  "社交互动：纯聊天/点赞/打招呼，无实质信息",
        8:  "无意义标记：单字、表情、空内容",
        9:  "广告引流：推广、引流，无真实反馈",
        10: "无效表达：重复无意义内容",
    }
    noise_fill = PatternFill("solid", fgColor="FFF2CC")
    l16_fill   = PatternFill("solid", fgColor="E8F5E9")
    null_fill  = PatternFill("solid", fgColor="F5F5F5")

    for i, r in enumerate(noval_rows, 3):
        lid  = r["label_id"]
        fill = null_fill if lid is None else (l16_fill if lid <= 6 else noise_fill)
        vals = [lid if lid else "NULL", r["label_name"] or "-",
                r["cnt"], noval_desc.get(lid, "")]
        for j, v in enumerate(vals, 1):
            cell = ws5.cell(row=i, column=j, value=v)
            cell.fill   = fill
            cell.border = BORDER
            cell.alignment = CENTER if j in (1,3) else LEFT
            if j == 3:
                cell.number_format = "#,##0"

    auto_width(ws5)
    ws5.column_dimensions["D"].width = 45

    # ══════════════════════════════════════════════════════════════════
    # Sheet 6：示例评论
    # ══════════════════════════════════════════════════════════════════
    ws6 = wb.create_sheet("典型评论示例")

    ws6.merge_cells("A1:F1")
    t = ws6["A1"]
    t.value = "有价值评论 · 各 L1 高互动典型示例（reply_count Top5）"
    t.font  = Font(bold=True, size=13, color="2E4057")
    t.alignment = CENTER
    ws6.row_dimensions[1].height = 28

    write_headers(ws6, ["一级标签", "二级标签", "三级标签", "评论内容", "子回复数", "解读"], row=2)

    interp = {
        1: "家长关注辅食添加时机与引入顺序",
        2: "日常喂养中最常见的操作困惑",
        3: "宝宝食用后的直接身体反馈",
        4: "购买决策时的核心顾虑与比较",
        5: "自制辅食的操作细节与储存疑问",
    }

    for r in ex_rows:
        l1_id = r["l1_tag_id"]
        color = L1_COLORS.get(l1_id, "CCCCCC")
        fill  = row_fill(color)
        vals  = [r["l1_name"], r["l2_tag_name"] or "-",
                 r["l3_tag_name"] or "-",
                 (r["content"] or "")[:200],
                 r["reply_count"],
                 interp.get(l1_id, "")]
        row_n = ws6.max_row + 1
        for j, v in enumerate(vals, 1):
            cell = ws6.cell(row=row_n, column=j, value=v)
            cell.fill      = fill
            cell.border    = BORDER
            cell.alignment = CENTER if j == 5 else LEFT
            if j == 5:
                cell.number_format = "#,##0"
        ws6.row_dimensions[row_n].height = 40

    auto_width(ws6)
    ws6.column_dimensions["D"].width = 50
    ws6.column_dimensions["F"].width = 25

    # ── 保存 ──
    out_dir  = r"E:\work\小红书爬虫"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "评论分布分析.xlsx")
    wb.save(out_path)
    print(f"已保存：{out_path}")


if __name__ == "__main__":
    main()
