# -*- coding: utf-8 -*-
"""
翻译小站 —— 把中文成稿(overview 两节 + 选定研究目标 + design 四节)忠实译成学术英文

设计:翻译而非重新生成——内容与中文版一一对应,不会漂移。逐节翻译存 output/plan_en.json,
make_plans.py 检测到该文件且为选定稿时,自动另出 traceability_and_result/plan_final_en.pdf。
人工复核清单不翻译(内部工作笔记,以中文版为准)。

运行条件:overview.txt、research_goal.txt、selected_goal.json、design.txt 均已生成。
用法(plan_gen 目录下): python translate_en.py
"""

import re
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import goal_gen as gg          # 复用 call_llm / OUT_DIR

# call_llm 会把输出语言指令追加进系统提示;翻译任务必须覆盖成英文指令,
# 否则默认的"一律用中文"会把译文摁回中文(开关实现在 llm_core.set_out_lang)
gg.set_out_lang("Output the translation in English only.")

OUT_DIR = gg.OUT_DIR

TRANS_SYS = (
    "你是严谨的学术翻译。把中文申报书文本忠实翻译成规范的学术英文:"
    "不增删内容,不改动任何数字与指标;方法/数据集/指标等专有名词用其通用英文写法;"
    "'拟定/预期/待论证'的语气译为 proposed / expected / to be determined;"
    "保持原有段落划分。只输出译文,不要任何说明或前言。"
)


def _clean(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"```(?:\w+)?", "", text).strip()
    text = re.sub(r"^\s*(here is|below is|the following is|translation|好的|以下是)[^\n]*?[::]\s*",
                  "", text, flags=re.IGNORECASE).strip()
    return text


def translate(label, text):
    print(f"  译 {label} ({len(text)} 字)...", flush=True)
    out = _clean(gg.call_llm(TRANS_SYS, "原文:\n" + text, gg.TEMP_A, max_retries=8))
    print(f"    完成 ({len(out)} chars)")
    return out


def _strip_checklist(raw):
    return re.split(r"\n=+\n", raw, maxsplit=1)[0].strip()


def main():
    # ---- overview 两节 ----
    ov = _strip_checklist((OUT_DIR / "overview.txt").read_text(encoding="utf-8"))
    m = re.search(r"[((]一[))]需求分析\s*\n(.*?)\n\s*[((]二[))]研究现状\s*\n(.*)",
                  ov, flags=re.DOTALL)
    if not m:
        sys.exit("[缺料] overview.txt 里找不到两节结构,请先跑 overview_gen")
    xuqiu, xianzhuang = m.group(1).strip(), m.group(2).strip()

    # ---- 选定研究目标 ----
    sel_p = OUT_DIR / "selected_goal.json"
    if not sel_p.exists():
        sys.exit("[未选定] 没找到 selected_goal.json,请先在 goal_gen/make_plans 里选定目标")
    idx = json.loads(sel_p.read_text(encoding="utf-8")).get("index")
    goal_raw = (OUT_DIR / "research_goal.txt").read_text(encoding="utf-8")
    segs = re.split(r"研究目标[一二三四五六七八九十]( {2}⚠ 待人工确认)?[::]\s*\n", goal_raw)
    bodies = [segs[i].strip() for i in range(2, len(segs), 2)]
    if not (isinstance(idx, int) and 1 <= idx <= len(bodies)):
        sys.exit(f"[异常] 选定编号 {idx} 对不上 research_goal.txt")
    goal_text = bodies[idx - 1]

    # ---- design 四节 ----
    dz = _strip_checklist((OUT_DIR / "design.txt").read_text(encoding="utf-8"))
    dsegs = re.split(r"(?m)^([((][一二三四五][))]\S+)\s*$", dz)
    design_secs = [(dsegs[j].strip(), dsegs[j + 1].strip())
                   for j in range(1, len(dsegs) - 1, 2)]
    if not design_secs:
        sys.exit("[缺料] design.txt 里没切出四节,请先跑 design_gen")

    # design 小标题用固定映射(确定性,不劳模型)
    SUB_EN = {"研究内容": "1. Research content", "思路方法": "2. Approach and methods",
              "比较优势": "3. Comparative advantages", "可行性": "4. Feasibility"}

    req = (json.loads((OUT_DIR / "overview_meta.json").read_text(encoding="utf-8"))
           .get("requirement", "")) if (OUT_DIR / "overview_meta.json").exists() else ""

    print(f"共 7~8 段待译,模型: {gg.MODEL}")
    en = {
        "requirement_en": translate("研究需求", req) if req else "",
        "xuqiu": translate("(一)需求分析", xuqiu),
        "xianzhuang": translate("(二)研究现状", xianzhuang),
        "goal": translate(f"(三)研究目标(选定第{idx}个)", goal_text),
        "design": [],
    }
    for sub, body in design_secs:
        name = re.sub(r"^[((][一二三四五][))]", "", sub)
        en["design"].append([SUB_EN.get(name, name), translate(f"研究方案·{name}", body)])

    (OUT_DIR / "plan_en.json").write_text(
        json.dumps(en, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n[已存盘] {OUT_DIR / 'plan_en.json'}")
    print("下一步: python make_plans.py 会自动另出 plan_final_en.pdf")


if __name__ == "__main__":
    main()
