# -*- coding: utf-8 -*-
"""
把 output/ 里的中间结果汇成一份"研究目标溯源报告"(标签随 goal_gen.LANG 中/英切换)。

生成 goal_traceability.html + .pdf —— 展示 原文 → A单元 → B空白 → 去重 → C候选 → 反思 → D成稿 → 锦标赛排名。

跑法(在 plan_gen 目录,先跑过 goal_gen.py 生成 output/):
  python make_report.py 综述文件.txt
"""

import sys
import json
import html
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
TR_DIR = HERE / "traceability_and_result"      # 溯源/结果 PDF 统一放这里
TR_DIR.mkdir(exist_ok=True)

LANG = "zh"                                    # 从 goal_gen.py 源码读 LANG,不导入(免触发 openai)
try:
    import re as _re
    _m = _re.search(r'^LANG\s*=\s*"(\w+)"', (HERE / "config.py").read_text(encoding="utf-8"), _re.M)
    if _m:
        LANG = _m.group(1)
except Exception:
    pass

_LABELS = {
    "zh": {
        "report_title": "研究目标生成 · 溯源报告", "from": "来源综述",
        "units_n": "单元", "gaps_n": "空白", "dedup_n": "去重", "cands_n": "候选",
        "s0": "0 · 输入:研究现状综述",
        "sA_pdf": "A · 方法单元", "sA": "A · 结构化拆解(方法单元)", "sB": "B · 研究空白(gap)",
        "sDedup": "去重 · 合并后",
        "sC_pdf": "C · 候选目标(含反思判定与排名)", "sC": "C · 候选研究目标(含反思判定与锦标赛排名)",
        "sD": "D · 最终研究目标(成稿)", "sT": "锦标赛 · 排名总表",
        "c_id": "id", "c_work": "方法", "c_origin": "国内外", "c_solves": "解决", "c_scene": "数据场景",
        "c_metrics": "定量指标", "c_limit": "局限",
        "rank": "排名", "total": "总分", "reflect": "反思", "goal": "研究目标", "keyprob": "拟解决关键问题",
        "qd": "定量增量", "metric": "指标", "cur": "现状", "tgt": "目标", "inc": "增量",
        "evid": "证据", "evid_unit": "证据单元", "reflect_reason": "反思理由", "rank_reason": "排名理由",
        "merged_from": "合并自", "evid_union": "证据并集", "tension": "张力", "involved": "涉及单元",
        "und": "待确定", "na": "—",
        "t_rank": "排名", "t_gap": "gap", "t_total": "总分", "t_evi": "依据", "t_sig": "价值",
        "t_fea": "可行", "t_reason": "理由", "notfound": "(未找到综述文件)",
    },
    "en": {
        "report_title": "Research Goal Generation · Traceability Report", "from": "Source review",
        "units_n": "units", "gaps_n": "gaps", "dedup_n": "deduped", "cands_n": "candidates",
        "s0": "0 · Input: Literature Review",
        "sA_pdf": "A · Method Units", "sA": "A · Structured Extraction (Method Units)", "sB": "B · Research Gaps",
        "sDedup": "Dedup · Merged",
        "sC_pdf": "C · Candidate Goals (reflection + ranking)", "sC": "C · Candidate Research Goals (reflection + ranking)",
        "sD": "D · Final Research Goals", "sT": "Tournament · Ranking",
        "c_id": "id", "c_work": "method", "c_origin": "origin", "c_solves": "solves", "c_scene": "data/setting",
        "c_metrics": "metrics", "c_limit": "limitation",
        "rank": "rank", "total": "total", "reflect": "reflection", "goal": "objective", "keyprob": "key problems",
        "qd": "quant. delta", "metric": "metric", "cur": "current", "tgt": "target", "inc": "increment",
        "evid": "evidence", "evid_unit": "evidence units", "reflect_reason": "reflection note", "rank_reason": "ranking note",
        "merged_from": "merged from", "evid_union": "evidence union", "tension": "tension", "involved": "units",
        "und": "TBD", "na": "—",
        "t_rank": "rank", "t_gap": "gap", "t_total": "total", "t_evi": "evidence", "t_sig": "significance",
        "t_fea": "feasibility", "t_reason": "note", "notfound": "(review file not found)",
    },
}
L = _LABELS.get(LANG, _LABELS["zh"])


def _vclass(v):
    s = str(v).strip().lower()
    if v in ("通过",) or s == "pass":
        return "pass"
    if v in ("标记",) or s == "flag":
        return "flag"
    if v in ("淘汰",) or s == "reject":
        return "drop"
    return "muted"


def load(name, default=None):
    p = OUT / name
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def esc(x):
    return html.escape("" if x is None else str(x))


CJK_FONTS = [
    ("SimHei", r"C:\Windows\Fonts\simhei.ttf", 0),
    ("MSYH", r"C:\Windows\Fonts\msyh.ttc", 0),
    ("SimSun", r"C:\Windows\Fonts\simsun.ttc", 0),
]


def _register_cjk():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for name, path, idx in CJK_FONTS:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont(name, path, subfontIndex=idx))
                return name
            except Exception:
                continue
    return None


def build_pdf(review, review_path, units, gaps, merged, cands, refl_by, tour_by, goal_txt, tourney):
    """用 reportlab 直接出 PDF(需 Windows 字体;SimHei 也能渲染英文)。成功返回 True。"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        return False
    font = _register_cjk()
    if not font:
        return False

    _SUP = {"⁰": "^0", "¹": "^1", "²": "^2", "³": "^3", "⁴": "^4", "⁵": "^5",
            "⁶": "^6", "⁷": "^7", "⁸": "^8", "⁹": "^9", "ⁿ": "^n"}

    def rp(x):
        s = "" if x is None else str(x)
        for k, v in _SUP.items():        # 字体缺上标字形 → 用 ^n,保证显示
            s = s.replace(k, v)
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return s.replace("\n", "<br/>")

    h1 = ParagraphStyle("h1", fontName=font, fontSize=18, spaceAfter=6, textColor=colors.HexColor("#0f6e56"))
    h2 = ParagraphStyle("h2", fontName=font, fontSize=13, spaceBefore=12, spaceAfter=4, textColor=colors.HexColor("#0f6e56"))
    body = ParagraphStyle("body", fontName=font, fontSize=9.5, leading=15)
    small = ParagraphStyle("small", fontName=font, fontSize=8, leading=12, textColor=colors.HexColor("#666666"))
    cell = ParagraphStyle("cell", fontName=font, fontSize=8, leading=11)

    story = [Paragraph(L["report_title"], h1),
             Paragraph(f'{L["from"]}: {rp(review_path.name)}　|　{len(units)} {L["units_n"]} · {len(gaps)} {L["gaps_n"]} → {len(merged) or len(gaps)} {L["dedup_n"]} · {len(cands)} {L["cands_n"]}', small),
             Spacer(1, 4)]

    story.append(Paragraph(L["s0"], h2))
    story.append(Paragraph(rp(review), body))

    story.append(Paragraph(L["sA_pdf"], h2))
    data = [[Paragraph(f"<b>{L['c_id']}</b>", cell), Paragraph(f"<b>{L['c_work']}</b>", cell),
             Paragraph(f"<b>{L['c_origin']}</b>", cell), Paragraph(f"<b>{L['c_metrics']}</b>", cell),
             Paragraph(f"<b>{L['c_limit']}</b>", cell)]]
    for u in units:
        metrics = "; ".join(f"{m.get('name')}={m.get('value')}" for m in (u.get("metrics") or [])) or L["na"]
        data.append([Paragraph(rp(u.get("id")), cell), Paragraph(rp(u.get("work")), cell),
                     Paragraph(rp(u.get("origin")), cell), Paragraph(rp(metrics), cell),
                     Paragraph(rp(u.get("limitation") or L["na"]), cell)])
    tbl = Table(data, colWidths=[14*mm, 30*mm, 14*mm, 40*mm, 72*mm], repeatRows=1)
    tbl.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                             ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e1f5ee")),
                             ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(tbl)

    story.append(Paragraph(L["sB"], h2))
    for g in gaps:
        story.append(Paragraph(f"<b>{rp(g.get('gap_id'))} · {rp(g.get('type'))}</b>　{rp(g.get('summary'))}", body))
        story.append(Paragraph(f"{L['involved']} {rp(g.get('involved_units'))}　{L['tension']}: {rp(g.get('tension'))}", small))

    if merged:
        story.append(Paragraph(L["sDedup"], h2))
        for m in merged:
            src = m.get("merged_from", [])
            note = f"({L['merged_from']} {rp(src)})" if len(src) > 1 else ""
            story.append(Paragraph(f"<b>{rp(m.get('gap_id'))}</b> {note}　{rp(m.get('summary'))}", body))

    story.append(Paragraph(L["sC_pdf"], h2))
    for c in cands:
        gid = c.get("gap_id")
        r = refl_by.get(gid, {})
        t = tour_by.get(gid, {})
        qd = c.get("quantitative_delta") or {}
        rk = f"[{L['rank']} #{t.get('rank')} · {L['total']} {t.get('total')}] " if t else ""
        story.append(Paragraph(f"{rk}<b>{rp(gid)}</b>　{L['reflect']}: {rp(r.get('verdict', ''))}", body))
        story.append(Paragraph(f"<b>{L['goal']}:</b> {rp(c.get('objective'))}", body))
        story.append(Paragraph(f"<b>{L['keyprob']}:</b> {rp('; '.join(c.get('key_problems') or []))}", body))
        story.append(Paragraph(f"<b>{L['qd']}:</b> {rp(qd.get('metric') or L['na'])}; {L['cur']} {rp(qd.get('current_level') or L['na'])}; "
                               f"{L['tgt']} {rp(qd.get('target_level') or L['und'])}", body))
        story.append(Paragraph(f"{L['evid']} {rp(c.get('evidence_from_review'))}　{L['rank_reason']}: {rp(t.get('reason', ''))}", small))
        story.append(Spacer(1, 4))

    story.append(Paragraph(L["sD"], h2))
    story.append(Paragraph(rp(goal_txt), body))

    if tourney:
        story.append(Paragraph(L["sT"], h2))
        cols = [L["t_rank"], L["t_gap"], L["t_total"], L["t_evi"], L["t_sig"], L["t_fea"], L["t_reason"]]
        tdata = [[Paragraph(f"<b>{x}</b>", cell) for x in cols]]
        for t in tourney:
            sc = t.get("scores", {}) or {}
            tdata.append([Paragraph(rp(f"#{t.get('rank')}"), cell), Paragraph(rp(t.get("gap_id")), cell),
                          Paragraph(rp(t.get("total")), cell), Paragraph(rp(sc.get("evidence")), cell),
                          Paragraph(rp(sc.get("significance")), cell), Paragraph(rp(sc.get("feasibility")), cell),
                          Paragraph(rp(t.get("reason")), cell)])
        tt = Table(tdata, colWidths=[12*mm, 14*mm, 12*mm, 12*mm, 12*mm, 12*mm, 96*mm], repeatRows=1)
        tt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e1f5ee")),
                                ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(tt)

    doc = SimpleDocTemplate(str(TR_DIR / "goal_traceability.pdf"), pagesize=A4,
                            topMargin=15*mm, bottomMargin=15*mm, leftMargin=14*mm, rightMargin=14*mm)
    doc.build(story)
    return True


def main():
    review_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "tests" / "test_review_imputation.txt"
    review = review_path.read_text(encoding="utf-8") if review_path.exists() else L["notfound"]

    units = load("units.json", [])
    gaps = load("gaps.json", [])
    merged = load("gaps_merged.json", [])
    cands = load("candidates.json", [])
    refl = load("reflections.json", [])
    tourney = load("tournament.json", [])
    goal_txt = (OUT / "research_goal.txt").read_text(encoding="utf-8") if (OUT / "research_goal.txt").exists() else ""

    refl_by = {r.get("gap_id"): r for r in refl}
    tour_by = {t.get("gap_id"): t for t in tourney}

    lang_attr = "en" if LANG == "en" else "zh"
    parts = [f"""<!doctype html><html lang="{lang_attr}"><head><meta charset="utf-8">
<title>{esc(L['report_title'])}</title><style>
body{{font-family:"Microsoft YaHei","微软雅黑",Arial,sans-serif;max-width:900px;margin:24px auto;padding:0 20px;color:#1a1a1a;line-height:1.7}}
h1{{font-size:24px;border-bottom:3px solid #1d9e75;padding-bottom:8px}}
h2{{font-size:19px;margin-top:34px;color:#0f6e56;border-left:5px solid #1d9e75;padding-left:10px}}
.review{{background:#f5f5f0;padding:14px 16px;border-radius:8px;white-space:pre-wrap;font-size:14px}}
table{{border-collapse:collapse;width:100%;margin:10px 0;font-size:13px}}
th,td{{border:1px solid #ddd;padding:7px 9px;text-align:left;vertical-align:top}}
th{{background:#e1f5ee}}
.card{{border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin:12px 0}}
.pass{{color:#0f6e56;font-weight:bold}}.flag{{color:#ba7517;font-weight:bold}}.drop{{color:#a32d2d;font-weight:bold}}
.rank{{display:inline-block;background:#1d9e75;color:#fff;border-radius:4px;padding:1px 8px;font-weight:bold}}
.muted{{color:#777;font-size:12px}}
.goal{{white-space:pre-wrap;background:#fafafa;padding:12px 16px;border-radius:8px;border-left:4px solid #1d9e75}}
</style></head><body>"""]

    parts.append(f"<h1>{esc(L['report_title'])}</h1>")
    parts.append(f'<p class="muted">{esc(L["from"])}: {esc(review_path.name)}　|　{len(units)} {esc(L["units_n"])} · {len(gaps)} {esc(L["gaps_n"])} → {len(merged) or len(gaps)} {esc(L["dedup_n"])} · {len(cands)} {esc(L["cands_n"])}</p>')

    parts.append(f"<h2>{esc(L['s0'])}</h2>")
    parts.append(f'<div class="review">{esc(review)}</div>')

    parts.append(f"<h2>{esc(L['sA'])}</h2>")
    parts.append(f"<table><tr><th>{esc(L['c_id'])}</th><th>{esc(L['c_work'])}</th><th>{esc(L['c_origin'])}</th>"
                 f"<th>{esc(L['c_solves'])}</th><th>{esc(L['c_scene'])}</th><th>{esc(L['c_metrics'])}</th><th>{esc(L['c_limit'])}</th></tr>")
    for u in units:
        metrics = "; ".join(f"{m.get('name')}={m.get('value')}" for m in (u.get("metrics") or [])) or L["na"]
        parts.append("<tr>"
                     f"<td>{esc(u.get('id'))}</td><td>{esc(u.get('work'))}</td><td>{esc(u.get('origin'))}</td>"
                     f"<td>{esc(u.get('solves'))}</td><td>{esc(u.get('data_scene') or L['na'])}</td>"
                     f"<td>{esc(metrics)}</td><td>{esc(u.get('limitation') or L['na'])}</td></tr>")
    parts.append("</table>")

    parts.append(f"<h2>{esc(L['sB'])}</h2>")
    for g in gaps:
        parts.append(f'<div class="card"><b>{esc(g.get("gap_id"))} · {esc(g.get("type"))}</b><br>'
                     f'{esc(g.get("summary"))}<br>'
                     f'<span class="muted">{esc(L["involved"])} {esc(g.get("involved_units"))}　{esc(L["tension"])}: {esc(g.get("tension"))}</span></div>')

    if merged:
        parts.append(f"<h2>{esc(L['sDedup'])}</h2>")
        for m in merged:
            src = m.get("merged_from", [])
            note = f"({esc(L['merged_from'])} {esc(src)})" if len(src) > 1 else ""
            parts.append(f'<div class="card"><b>{esc(m.get("gap_id"))}</b> {note}<br>{esc(m.get("summary"))}<br>'
                         f'<span class="muted">{esc(L["evid_union"])} {esc(m.get("involved_units"))}</span></div>')

    parts.append(f"<h2>{esc(L['sC'])}</h2>")
    for c in cands:
        gid = c.get("gap_id")
        r = refl_by.get(gid, {})
        v = r.get("verdict", "")
        vcls = _vclass(v)
        t = tour_by.get(gid, {})
        rank_html = f'<span class="rank">{esc(L["rank"])} #{t.get("rank")} · {esc(L["total"])} {t.get("total")}</span> ' if t else ""
        qd = c.get("quantitative_delta") or {}
        problems = "; ".join(c.get("key_problems") or [])
        parts.append('<div class="card">')
        parts.append(f'{rank_html}<b>{esc(gid)}</b>　<span class="{vcls}">{esc(L["reflect"])}: {esc(v)}</span>')
        parts.append(f'<br><b>{esc(L["goal"])}:</b>{esc(c.get("objective"))}')
        parts.append(f'<br><b>{esc(L["keyprob"])}:</b>{esc(problems)}')
        parts.append(f'<br><b>{esc(L["qd"])}:</b>{esc(L["metric"])} {esc(qd.get("metric") or L["na"])}; {esc(L["cur"])} {esc(qd.get("current_level") or L["na"])}; '
                     f'{esc(L["tgt"])} {esc(qd.get("target_level") or L["und"])}; {esc(L["inc"])} {esc(qd.get("increment") or L["und"])}')
        parts.append(f'<br><span class="muted">{esc(L["evid_unit"])} {esc(c.get("evidence_from_review"))}'
                     f'　{esc(L["reflect_reason"])}: {esc(r.get("reason", ""))}　{esc(L["rank_reason"])}: {esc(t.get("reason", ""))}</span>')
        parts.append('</div>')

    parts.append(f"<h2>{esc(L['sD'])}</h2>")
    parts.append(f'<div class="goal">{esc(goal_txt)}</div>')

    if tourney:
        parts.append(f"<h2>{esc(L['sT'])}</h2>")
        parts.append(f"<table><tr><th>{esc(L['t_rank'])}</th><th>{esc(L['t_gap'])}</th><th>{esc(L['t_total'])}</th>"
                     f"<th>{esc(L['t_evi'])}</th><th>{esc(L['t_sig'])}</th><th>{esc(L['t_fea'])}</th><th>{esc(L['t_reason'])}</th></tr>")
        for t in tourney:
            sc = t.get("scores", {}) or {}
            parts.append(f'<tr><td>#{esc(t.get("rank"))}</td><td>{esc(t.get("gap_id"))}</td><td>{esc(t.get("total"))}</td>'
                         f'<td>{esc(sc.get("evidence"))}</td><td>{esc(sc.get("significance"))}</td><td>{esc(sc.get("feasibility"))}</td>'
                         f'<td>{esc(t.get("reason"))}</td></tr>')
        parts.append("</table>")

    parts.append("</body></html>")

    outp = TR_DIR / "goal_traceability.html"
    outp.write_text("\n".join(parts), encoding="utf-8")
    print(f"generated {outp}")

    try:
        if build_pdf(review, review_path, units, gaps, merged, cands, refl_by, tour_by, goal_txt, tourney):
            print(f"generated {TR_DIR / 'goal_traceability.pdf'}")
        else:
            print("(no reportlab or font; open the HTML and print to PDF)")
    except Exception as e:
        print(f"(PDF failed: {e}; open the HTML and print to PDF)")


if __name__ == "__main__":
    main()
