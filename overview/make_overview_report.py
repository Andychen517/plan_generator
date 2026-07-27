# -*- coding: utf-8 -*-
"""
概述溯源报告 —— 把 overview_gen 的一条链摊开成 PDF:
  方法单元(A 步) -> 三镜头评审记录(逐轮,含问题/原文/修改指令) -> 终稿(需求分析+研究现状)

读取 output\ 下 overview_gen 的产物:
  overview_units.json / overview_review_r*.json / overview_meta.json / overview.txt

用法(在 plan_gen 目录下):
  python overview\\make_overview_report.py
产出:
  traceability_and_result\\overview_traceability.pdf
"""

import json
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak)

ROOT = Path(__file__).resolve().parent.parent      # goal_gen 根目录
OUT_DIR = ROOT / "output"
TR_DIR = ROOT / "traceability_and_result"
TR_DIR.mkdir(exist_ok=True)
PDF_PATH = TR_DIR / "overview_traceability.pdf"

# ---------------------------------------------------------------- 字体(中文)
FONT = None
for name, path in [("MSYH", r"C:\Windows\Fonts\msyh.ttc"),
                   ("SimHei", r"C:\Windows\Fonts\simhei.ttf"),
                   ("SimSun", r"C:\Windows\Fonts\simsun.ttc")]:
    try:
        pdfmetrics.registerFont(TTFont(name, path, subfontIndex=0))
        FONT = name
        break
    except Exception:
        continue
if not FONT:
    raise SystemExit("找不到可用中文字体(需要 msyh/simhei/simsun 之一)")

GREEN = colors.HexColor("#0f6e56")
GREY = colors.HexColor("#666666")
title_st = ParagraphStyle("t", fontName=FONT, fontSize=16, leading=22, textColor=GREEN)
meta_st = ParagraphStyle("m", fontName=FONT, fontSize=9, leading=14, textColor=GREY)
h1_st = ParagraphStyle("h1", fontName=FONT, fontSize=13, leading=18,
                       spaceBefore=10, spaceAfter=4, textColor=GREEN)
h2_st = ParagraphStyle("h2", fontName=FONT, fontSize=11, leading=15,
                       spaceBefore=6, spaceAfter=3, textColor=colors.HexColor("#333333"))
body_st = ParagraphStyle("b", fontName=FONT, fontSize=9.5, leading=14.5)
cell_st = ParagraphStyle("c", fontName=FONT, fontSize=8, leading=11)
cellg_st = ParagraphStyle("cg", fontName=FONT, fontSize=8, leading=11, textColor=GREY)


def esc(s) -> str:
    return str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load(name):
    p = OUT_DIR / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def make_table(header, rows, widths):
    data = [[Paragraph(f"<b>{esc(h)}</b>", cell_st) for h in header]] + rows
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f3ef")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return t


story = [Paragraph("概述溯源报告(overview_gen)", title_st)]

meta = load("overview_meta.json") or {}
meta_line = (f"研究需求:{esc(meta.get('requirement', '(未记录)'))}  ·  "
             f"综述长度:{meta.get('review_chars', '?')} 字  ·  "
             f"评审轮次:{meta.get('rounds', '?')}  ·  "
             f"最终{'通过' if meta.get('passed') else '经修订出稿(建议人工复核)'}")
story += [Paragraph(meta_line, meta_st), Spacer(1, 4)]

# ------------------------------------------------- 一、方法单元(证据底座)
units = load("units.json") or load("overview_units.json") or []   # 新版共用 units.json;旧文件名兜底
story.append(Paragraph(f"一、方法单元(A 步结构化拆解,共 {len(units)} 个——两节正文的证据底座)", h1_st))
rows = []
for u in units:
    metrics = u.get("metrics") or []
    mtxt = ";".join(f"{m.get('name')}={m.get('value')}" for m in metrics if isinstance(m, dict)) or "—"
    rows.append([
        Paragraph(f"<b>{esc(u.get('id'))}</b> {esc(u.get('work'))}", cell_st),
        Paragraph(esc(u.get("origin") or "未知"), cell_st),
        Paragraph(esc(mtxt), cell_st),
        Paragraph(esc((u.get("limitation") or "")[:160]), cellg_st),
    ])
story.append(make_table(["单元/方法", "国内外", "定量指标", "局限(节选)"],
                        rows, [46 * mm, 14 * mm, 52 * mm, 66 * mm]))

# ------------------------------------------------- 二、三镜头评审记录(逐轮)
story.append(Paragraph("二、三镜头评审记录(一致性 / 忠实性 / 表达规范)", h1_st))
rnd = 0
while True:
    rnd += 1
    rev = load(f"overview_review_r{rnd}.json")
    if rev is None:
        break
    issues = rev.get("issues", []) or []
    sk = rev.get("skeleton") or {}
    story.append(Paragraph(f"第 {rnd} 轮:共 {len(issues)} 条问题", h2_st))
    if sk:
        qdims = ";".join("、".join(q.get("covers_dims", [])) or "?"
                         for q in sk.get("research_questions", []))
        story.append(Paragraph(
            f"骨架:场景「{esc(sk.get('scene'))}」 主线维度 {esc('、'.join(sk.get('mainline_dims', [])))} "
            f"/ 研究问题覆盖 {esc(qdims)} / 结论维度 {esc('、'.join(sk.get('conclusion_dims', [])))}",
            cellg_st))
    if issues:
        rows = [[
            Paragraph(f"{esc(it.get('lens'))}{esc(it.get('check', ''))}·{esc(it.get('section'))}", cell_st),
            Paragraph(esc(it.get("problem")), cell_st),
            Paragraph(esc((it.get("quote") or "")[:120]), cellg_st),
            Paragraph(esc(it.get("fix")), cell_st),
        ] for it in issues]
        story.append(make_table(["镜头·节", "问题", "原文(节选)", "修改指令"],
                                rows, [26 * mm, 50 * mm, 46 * mm, 56 * mm]))
    else:
        story.append(Paragraph("(本轮无问题,评审通过)", cellg_st))
    story.append(Spacer(1, 4))
if rnd == 1:
    story.append(Paragraph("(未找到评审记录 overview_review_r*.json)", cellg_st))

# ------------------------------------------------- 三、终稿
story.append(PageBreak())
story.append(Paragraph("三、终稿(经上述评审与修订后出稿)", h1_st))
final_txt = (OUT_DIR / "overview.txt")
if final_txt.exists():
    for para in final_txt.read_text(encoding="utf-8").split("\n"):
        if not para.strip():
            story.append(Spacer(1, 5))
            continue
        if para.strip().startswith(("(一)", "(二)", "(一)", "(二)")):
            story.append(Paragraph(esc(para.strip()), h2_st))
        else:
            story.append(Paragraph(esc(para.strip()), body_st))
else:
    story.append(Paragraph("(未找到 overview.txt)", cellg_st))

doc = SimpleDocTemplate(str(PDF_PATH), pagesize=A4,
                        leftMargin=14 * mm, rightMargin=12 * mm,
                        topMargin=14 * mm, bottomMargin=14 * mm)
doc.build(story)
print(f"已生成 {PDF_PATH}")
