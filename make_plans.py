# -*- coding: utf-8 -*-
"""
拼方案 PDF —— 把 overview_gen 的两节 + goal_gen 的研究目标拼成完整方案:
  plan1.pdf / plan2.pdf / plan3.pdf(每份 = 需求分析 + 研究现状 + 一个研究目标)
选定稿模式(plan_final.pdf)下,若 output/design.txt 存在,追加"(四)研究方案"——
design_gen 的四节以小标题分段排入,其人工复核清单并进文末附录(2026-07-24 接入)。

读取 output\ 下:
  overview.txt(两节 + 人工复核清单)、research_goal.txt(2~3 个研究目标)、
  reflections.json + tournament.json(把锦标赛排名标到对应方案上)、overview_meta.json

用法:
  python make_plans.py
产出:
  plan1.pdf、plan2.pdf、plan3.pdf(本目录;有几个目标出几份)
"""

import json
import re
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "output"

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

from reportlab.lib.enums import TA_JUSTIFY

GREEN = colors.HexColor("#0f6e56")
GREY = colors.HexColor("#666666")
# wordWrap="CJK":中英混排按字断行,避免英文括注被整块甩到下一行
title_st = ParagraphStyle("t", fontName=FONT, fontSize=18, leading=26, textColor=GREEN)
meta_st = ParagraphStyle("m", fontName=FONT, fontSize=9, leading=14, textColor=GREY,
                         wordWrap="CJK")
h1_st = ParagraphStyle("h1", fontName=FONT, fontSize=13, leading=18,
                       spaceBefore=12, spaceAfter=5, textColor=GREEN)
# 小标题:研究方案内部的(一)~(四)分段用,比大节标题小一号
h2_st = ParagraphStyle("h2", fontName=FONT, fontSize=11.5, leading=16,
                       spaceBefore=8, spaceAfter=3, textColor=GREEN)
body_st = ParagraphStyle("b", fontName=FONT, fontSize=10.5, leading=17.5,
                         firstLineIndent=21, wordWrap="CJK", alignment=TA_JUSTIFY,
                         spaceAfter=2)
# 编号条目(如"1. 如何……"):悬挂缩进,编号顶格、折行对齐正文
item_st = ParagraphStyle("i", fontName=FONT, fontSize=10.5, leading=17.5,
                         firstLineIndent=0, leftIndent=21, wordWrap="CJK",
                         alignment=TA_JUSTIFY, spaceAfter=2)
note_st = ParagraphStyle("n", fontName=FONT, fontSize=8.5, leading=12.5, textColor=GREY,
                         wordWrap="CJK")


def esc(s) -> str:
    t = str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # 正文里偶带 markdown 粗体标记,转成 reportlab 的 <b> 标签(不转会显示星号)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


def load_json(name):
    p = OUT_DIR / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# ---------------------------------------------------------------- 读材料
overview_raw = (OUT_DIR / "overview.txt").read_text(encoding="utf-8")
# 切掉人工复核清单区块(单独作附录)
parts = re.split(r"\n=+\n", overview_raw, maxsplit=1)
overview_body = parts[0].strip()
review_block = parts[1].strip() if len(parts) > 1 else ""

m = re.search(r"[((]一[))]需求分析\s*\n(.*?)\n\s*[((]二[))]研究现状\s*\n(.*)",
              overview_body, flags=re.DOTALL)
if not m:
    raise SystemExit("overview.txt 里找不到 (一)需求分析 / (二)研究现状 结构")
xuqiu, xianzhuang = m.group(1).strip(), m.group(2).strip()

# 研究方案(design_gen 产物,对"选定的那一个目标"展开;可能不存在)
design_secs, design_notes = [], []          # [(小标题, 正文)], 复核清单条目
design_p = OUT_DIR / "design.txt"
if design_p.exists():
    d_parts = re.split(r"\n=+\n", design_p.read_text(encoding="utf-8"), maxsplit=1)
    if len(d_parts) > 1:
        design_notes = [l.strip() for l in d_parts[1].split("\n")
                        if l.strip() and not l.startswith("【")]
    # 按"(一)xxx"标题行切成小节;标题原样保留当小标题
    segs = re.split(r"(?m)^([((][一二三四五][))]\S+)\s*$", d_parts[0].strip())
    for _j in range(1, len(segs) - 1, 2):
        design_secs.append((segs[_j].strip(), segs[_j + 1].strip()))
    if not design_secs:
        print("[提示] design.txt 存在但没切出 (一)~(四) 小节,方案部分跳过")

goal_raw = (OUT_DIR / "research_goal.txt").read_text(encoding="utf-8")
# 切成一个个目标:研究目标一/二/三(可能带 ⚠ 待人工确认)
goal_parts = re.split(r"研究目标([一二三四五六七八九十])( {2}⚠ 待人工确认)?[::]\s*\n", goal_raw)
goals = []          # [(标号, 是否标记, 正文), ...]
i = 1
while i + 2 <= len(goal_parts):
    goals.append((goal_parts[i], bool(goal_parts[i + 1]), goal_parts[i + 2].strip()))
    i += 3
if not goals:
    raise SystemExit("research_goal.txt 里没切出任何研究目标")

# 锦标赛排名:成稿顺序 -> 幸存者 gap_id -> tournament 里的名次
reflections = load_json("reflections.json") or []
tournament = load_json("tournament.json") or []
survivor_gaps = [r.get("gap_id") for r in reflections if r.get("verdict") != "淘汰"]
rank_by_gap = {t.get("gap_id"): t for t in tournament}

meta = load_json("overview_meta.json") or {}
req = meta.get("requirement", "")

# 用户在 goal_gen 锦标赛后的互动窗口选定了目标 → 只出那一份(plan_final.pdf)
sel = load_json("selected_goal.json")
items = list(enumerate(goals, 1))
single = isinstance(sel, dict) and isinstance(sel.get("index"), int) \
    and 1 <= sel["index"] <= len(goals)
if single:
    items = [items[sel["index"] - 1]]
    print(f"检测到选定目标(第 {sel['index']} 个),只生成该目标的方案")
elif sys.stdin.isatty() and len(goals) > 1:
    # 交互兜底:goal_gen 里的选择窗口若被"整块粘贴"的后续命令吃掉了输入,这里还能选
    print("未检测到选定目标,现在选也可以:")
    for idx, (label, marked, gtext) in items:
        gap_id = survivor_gaps[idx - 1] if idx - 1 < len(survivor_gaps) else None
        t = rank_by_gap.get(gap_id) or {}
        flag = "(⚠ 待人工确认)" if marked else ""
        print(f"  [{idx}] 研究目标{label}{flag} 锦标赛第 {t.get('rank', '?')} 名: {gtext[:50]}...")
    ans = input("输入编号只生成该目标的方案(直接回车=全部生成): ").strip()
    if ans.isdigit() and 1 <= int(ans) <= len(goals):
        i = int(ans)
        single = True
        items = [(i, goals[i - 1])]
        (OUT_DIR / "selected_goal.json").write_text(
            json.dumps({"index": i}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  已选定研究目标{goals[i - 1][0]},只生成 plan_final.pdf")

# ---------------------------------------------------------------- 英文版询问(全链唯一的语言开关)
# 生成链只出中文;要英文就在这里现场把成稿翻译了(translate_en),不走语言切换重新生成
if single:
    en_probe = load_json("plan_en.json")
    design_p = OUT_DIR / "design.txt"
    if en_probe and design_p.exists() \
            and (OUT_DIR / "plan_en.json").stat().st_mtime < design_p.stat().st_mtime:
        print("[提示] plan_en.json 早于当前 design.txt,英文翻译可能过时;建议重跑 python translate_en.py")
    if not en_probe and sys.stdin.isatty():
        ans = input("需要附英文版吗?(y=现在翻译并生成 plan_final_en.pdf,约几分钟 / 回车=只出中文): ").strip().lower()
        if ans == "y":
            try:
                import translate_en
                translate_en.main()
            except SystemExit as e:          # 缺料时翻译站会报因退出,不拖垮排版
                print(f"[翻译未完成] {e}")

# ---------------------------------------------------------------- 逐个出 PDF
for idx, (label, marked, goal_text) in items:
    head_title = f"研究方案(选定稿:研究目标{label})" if single else f"研究方案 Plan {idx}"
    story = [Paragraph(head_title, title_st),
             Paragraph(f"研究需求:{esc(req)}", meta_st),
             Paragraph("生成:OpenProvHop 综述 → overview_gen(需求分析/研究现状,三镜头质量闸)"
                       " + goal_gen(研究目标,七步管线)"
                       + (" + design_gen(研究方案四节)" if single and design_secs else ""),
                       meta_st),
             Spacer(1, 6)]

    def add_prose(text):
        for p in text.split("\n"):
            p = p.strip()
            if not p:
                continue
            # 编号条目用悬挂缩进样式,普通段落用首行缩进
            st = item_st if re.match(r"^\d+[.、,)]", p) else body_st
            story.append(Paragraph(esc(p), st))

    story.append(Paragraph("(一)需求分析", h1_st))
    add_prose(xuqiu)

    story.append(Paragraph("(二)研究现状", h1_st))
    add_prose(xianzhuang)

    head = "(三)研究目标"
    if marked:
        head += "(⚠ 反思标记:待人工确认)"
    story.append(Paragraph(head, h1_st))
    add_prose(goal_text)

    # 锦标赛信息行
    gap_id = survivor_gaps[idx - 1] if idx - 1 < len(survivor_gaps) else None
    t = rank_by_gap.get(gap_id)
    if t:
        sc = t.get("scores", {}) or {}
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"锦标赛评审:第 {t.get('rank')} 名 / 共 {len(tournament)} 个方案 · 总分 {t.get('total')}"
            f"(依据强度 {sc.get('evidence')} / 研究价值 {sc.get('significance')} / 可行性 {sc.get('feasibility')})"
            f" · {esc(t.get('reason', ''))}", note_st))

    # (四)研究方案:design 是对"选定目标"展开的,只在选定稿里附;内部四节排成小标题
    attach_design = single and design_secs
    if attach_design:
        story.append(Paragraph("(四)研究方案", h1_st))
        for sub, text in design_secs:
            story.append(Paragraph(esc(sub), h2_st))
            add_prose(text)

    # 附录:人工复核清单(概述 + 研究方案两部分合并)
    d_notes = design_notes if attach_design else []
    if review_block or d_notes:
        story.append(Spacer(1, 8))
        story.append(Paragraph("附:人工复核清单(交稿前逐条处理后删除本附录)", h1_st))
        for line in review_block.split("\n"):
            if line.strip() and not line.startswith("【"):
                story.append(Paragraph(esc(line.strip()), note_st))
        if d_notes:
            story.append(Paragraph("· 以下来自研究方案(design_gen):", note_st))
            for line in d_notes:
                story.append(Paragraph(esc(line), note_st))

    tr_dir = HERE / "traceability_and_result"
    tr_dir.mkdir(exist_ok=True)
    pdf_path = tr_dir / ("plan_final.pdf" if single else f"plan{idx}.pdf")
    SimpleDocTemplate(str(pdf_path), pagesize=A4,
                      leftMargin=18 * mm, rightMargin=16 * mm,
                      topMargin=16 * mm, bottomMargin=16 * mm).build(story)
    rank_txt = f"(锦标赛第 {t.get('rank')} 名)" if t else ""
    print(f"已生成 {pdf_path} {rank_txt}")

# ---------------------------------------------------------------- 英文版(可选)
# translate_en.py 产出 output/plan_en.json 后,选定稿模式自动另出 plan_final_en.pdf
en = load_json("plan_en.json")
if single and en:
    # 英文正文用单词换行(不能用 CJK 逐字换行,会把英文单词从中间掰断)
    en_body_st = ParagraphStyle("eb", fontName=FONT, fontSize=10.5, leading=15.5,
                                firstLineIndent=18, alignment=TA_JUSTIFY, spaceAfter=3)

    def add_en(st_list, text):
        for p in text.split("\n"):
            if p.strip():
                st_list.append(Paragraph(esc(p.strip()), en_body_st))

    story2 = [Paragraph("Research Proposal (Selected Objective)", title_st),
              Paragraph(f"Research direction: {esc(en.get('requirement_en', ''))}", meta_st),
              Paragraph("English translation of the Chinese proposal; the Chinese version "
                        "and its review checklist remain authoritative.", note_st),
              Spacer(1, 6)]
    story2.append(Paragraph("I. Needs analysis", h1_st))
    add_en(story2, en.get("xuqiu", ""))
    story2.append(Paragraph("II. Research status", h1_st))
    add_en(story2, en.get("xianzhuang", ""))
    story2.append(Paragraph("III. Research objective", h1_st))
    add_en(story2, en.get("goal", ""))
    if en.get("design"):
        story2.append(Paragraph("IV. Research plan", h1_st))
        for sub, body in en["design"]:
            story2.append(Paragraph(esc(sub), h2_st))
            add_en(story2, body)
    en_path = HERE / "traceability_and_result" / "plan_final_en.pdf"
    SimpleDocTemplate(str(en_path), pagesize=A4,
                      leftMargin=18 * mm, rightMargin=16 * mm,
                      topMargin=16 * mm, bottomMargin=16 * mm).build(story2)
    print(f"已生成 {en_path}(英文版)")
elif en and not single:
    print("[提示] 检测到 plan_en.json 但未选定单一目标,英文版未生成(它只对应选定稿)")

print(f"共 {len(items)} 份方案" + (f"(从 {len(goals)} 个目标中选定)" if single else ""))
