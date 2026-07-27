# -*- coding: utf-8 -*-
"""
概述生成 —— 从 OpenProvHop 的综述产出申报书的前两节(中文)

对齐申报书模板:
  (一)需求分析:简要介绍本项目的研究背景或需求来源,分析提出研究问题
  (二)研究现状:客观简述国内外研究现状,重点聚焦与本项目核心问题相关的研究,
              注重定量描述,避免泛泛而谈

分工(2026-07-17 定):
  需求分析 <- 综述引言(背景) + goal_gen A 步 units(痛点):四段式
             现实需求 -> 障碍主线 -> 服务场景 -> 2~3个研究问题。
  研究现状 <- OpenProvHop 的 report 原文翻译重组:按"应用主题"分段,
             每段 原理->代表应用(国内外)->成效->局限->回扣本项目场景。

质量闸(2026-07-17 两轮人工评审固化而成,主题无关,换综述也生效):
  生成 -> 反思(三镜头评审团) -> 修订 -> 再反思 ... 最多两轮,通过才出稿。
    镜头1 一致性:抽文稿骨架(场景/主线/障碍/研究问题/结论),查五者对齐——
           声称的维度必须有研究问题覆盖、问题要素必须贴合场景、结论不许比问题大。
    镜头2 忠实性:数字语义不得改写、实体归属准确、指涉不明的数字删、
           证据与论点因果直接相关。
    镜头3 表达规范:数据密度/限定语来源/绝对化/拟定数值目标/异常指标/术语/语病/段落模板。
  另有代码 tripwire(确定性预检):数字溯源、密度统计、绝对化词表、近完美指标、
  研究问题带数值、两节数字重复。预检结果喂给镜头3复核。
  负对照见 test_overview_reflect.py:埋好缺陷看三镜头抓不抓得到,好稿不误杀。

用法:
  conda activate deepsearch
  cd E:\\ClaudeCode\\deep-research-python\\plan_gen
  python overview\\overview_gen.py openprovhop_review.txt "研究需求一句话"
"""

import re
import sys
import json
from pathlib import Path

# 本脚本在 goal_gen\overview\ 子目录,把上级目录加进搜索路径才能 import goal_gen
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import goal_gen as gg          # 复用 call_llm / parse_json / step_a(A 步) / OUT_DIR
from prompts_overview import *          # 提示词全部集中在 prompts_overview.py
from utils_overview import *            # 代码 tripwire(precheck/check_numbers)集中在 utils_overview.py
from utils_overview import _check_uid, _clean_prose   # 下划线名不随 * 导出,显式引入

# 全链固定中文出稿(英文版由 translate_en.py 翻译成稿),直接沿用 goal_gen 的语言指令

OUT_DIR = gg.OUT_DIR
from config import TEMP_OVERVIEW as TEMP_PROSE, MAX_REFLECT_ROUNDS   # 参数集中在 config.py


def _llm(system: str, user: str, temperature: float) -> str:
    """LLM 调用统一入口:重试提到 8 次(退避 3s~21s),扛代理瞬时断连。"""
    return gg.call_llm(system, user, temperature, max_retries=8)


# ================================================================== 生成 prompt





# ================================================================== 反思三镜头
# 每条 rubric 都是主题无关的通用标准,来自 2026-07-17 两轮人工评审的教训固化。









# ================================================================== 反思与修订步骤
def _draft_block(xuqiu: str, xianzhuang: str) -> str:
    return f"待审文稿:\n\n(一)需求分析:\n{xuqiu}\n\n(二)研究现状:\n{xianzhuang}\n"


def lens_consistency(xuqiu: str, xianzhuang: str, requirement: str):
    """镜头1 一致性:抽骨架,查 场景/主线/障碍/研究问题/结论 对齐。"""
    user = _draft_block(xuqiu, xianzhuang) + f"\n研究需求/方向:{requirement}\n" + LENS1_TAIL
    r = gg.parse_json(_llm(LENS1_SYS, user, gg.TEMP_A))
    return r.get("issues", []) or [], r.get("skeleton", {})


def lens_fidelity(xuqiu: str, xianzhuang: str, source_text: str):
    """镜头2 忠实性:对照来源材料查 语义/归属/指涉/证据相关。"""
    user = ("来源材料(文稿必须忠于它):\n" + source_text + "\n\n"
            + _draft_block(xuqiu, xianzhuang) + LENS2_TAIL)
    r = gg.parse_json(_llm(LENS2_SYS, user, gg.TEMP_A))
    return r.get("issues", []) or []


def lens_style(xuqiu: str, xianzhuang: str, hints: list):
    """镜头3 表达规范:密度/限定/拟定数值/措辞/术语/重复(预检警示供复核)。"""
    user = (_draft_block(xuqiu, xianzhuang)
            + "\n代码预检警示(供参考,可能有误报,请逐条判断):\n"
            + ("\n".join(hints) if hints else "(无)") + "\n" + LENS3_TAIL)
    r = gg.parse_json(_llm(LENS3_SYS, user, gg.TEMP_A))
    return r.get("issues", []) or []


def step_reflect(xuqiu: str, xianzhuang: str, source_text: str,
                 requirement: str, rnd: int):
    """三镜头评审,合并 issues。返回 (issues, skeleton)。"""
    print(f"\n===== 概述反思(第 {rnd} 轮):三镜头评审 =====")
    hints = precheck(xuqiu, xianzhuang)

    issues_c, skeleton = lens_consistency(xuqiu, xianzhuang, requirement)
    print(f"  镜头1 一致性: {len(issues_c)} 条")
    issues_f = lens_fidelity(xuqiu, xianzhuang, source_text)
    print(f"  镜头2 忠实性: {len(issues_f)} 条")
    issues_s = lens_style(xuqiu, xianzhuang, hints)
    print(f"  镜头3 表达: {len(issues_s)} 条")

    issues = issues_c + issues_f + issues_s
    for i, it in enumerate(issues, 1):
        print(f"  问题{i} [{it.get('lens')}{it.get('check', '')}|{it.get('section')}] "
              f"{it.get('problem')}")
        print(f"        原文: {it.get('quote')}")
        print(f"        修改: {it.get('fix')}")
    gg.dump(f"overview_review_r{rnd}", {"skeleton": skeleton, "issues": issues})
    return issues, skeleton


def step_revise(xuqiu: str, xianzhuang: str, issues) -> tuple:
    """按评审意见修订两节,返回 (新需求分析, 新研究现状)。切分失败则保留原稿。"""
    print("\n===== 概述修订:按评审意见精修 =====")
    user = (_draft_block(xuqiu, xianzhuang)
            + "\n评审意见(JSON,逐条修复其中的 issues):\n"
            + json.dumps(issues, ensure_ascii=False, indent=2) + REVISE_TAIL)
    text = _clean_prose(_llm(REVISE_SYS, user, TEMP_PROSE))
    m = re.search(r"[((]一[))]\s*需求分析\s*[::]?\s*\n(.*?)\n\s*[((]二[))]\s*研究现状\s*[::]?\s*\n(.*)",
                  text, flags=re.DOTALL)
    if not m:
        print("  [警告] 修订稿切分失败,保留原稿。原始返回已存 output/overview_revise_raw.txt")
        (OUT_DIR / "overview_revise_raw.txt").write_text(text, encoding="utf-8")
        return xuqiu, xianzhuang
    new_xq, new_xz = m.group(1).strip(), m.group(2).strip()
    print(f"  修订完成(需求分析 {len(new_xq)} 字,研究现状 {len(new_xz)} 字)")
    return new_xq, new_xz


# ================================================================== 两个生成步骤
def gen_xuqiu(units, review: str, requirement: str) -> str:
    print("\n===== 生成(一)需求分析(来源:综述引言 + A 步 units) =====")
    units_json = json.dumps(units, ensure_ascii=False, indent=2)
    user = XUQIU_USER.format(req=requirement, review=review, units=units_json)
    prose = _clean_prose(_llm(XUQIU_SYS, user, TEMP_PROSE))
    print(f"  完成 ({len(prose)} 字)")
    _check_uid(prose, "需求分析")
    check_numbers(prose, units_json + review, "需求分析")
    return prose


def gen_xianzhuang(review: str, requirement: str) -> str:
    print("\n===== 生成(二)研究现状(来源:report 原文) =====")
    user = XIANZHUANG_USER.format(req=requirement, review=review)
    prose = _clean_prose(_llm(XIANZHUANG_SYS, user, TEMP_PROSE))
    print(f"  完成 ({len(prose)} 字)")
    check_numbers(prose, review, "研究现状")
    return prose


# ================================================================== 主流程
def gen_overview(review: str, requirement: str):
    # A 步与 goal_gen 共用同一份 units.json(step_a 自带指纹缓存:
    # 同一份综述+同一套配置只抽一次,换综述/换语言自动重抽,两条线证据同源)
    units = gg.step_a(review)

    units_json = json.dumps(units, ensure_ascii=False, indent=2)
    source_text = units_json + "\n" + review          # 忠实性镜头 + 数字溯源的对照材料

    xuqiu = gen_xuqiu(units, review, requirement)
    xianzhuang = gen_xianzhuang(review, requirement)

    # 反思->修订循环:通过才出稿,最多 MAX_REFLECT_ROUNDS 轮
    passed = False
    last_issues = []
    for rnd in range(1, MAX_REFLECT_ROUNDS + 1):
        issues, _ = step_reflect(xuqiu, xianzhuang, source_text, requirement, rnd)
        if not issues:
            print(f"  第 {rnd} 轮评审通过,出稿")
            passed = True
            break
        last_issues = issues
        xuqiu, xianzhuang = step_revise(xuqiu, xianzhuang, issues)

    print("\n===== 出稿前最终核对 =====")
    leaks_xq = _check_uid(xuqiu, "需求分析")
    leaks_xz = _check_uid(xianzhuang, "研究现状")
    sus_xq = check_numbers(xuqiu, source_text, "需求分析")
    sus_xz = check_numbers(xianzhuang, review, "研究现状")
    hints = precheck(xuqiu, xianzhuang)
    flag = "" if passed else f"(经 {MAX_REFLECT_ROUNDS} 轮修订仍有问题被点名,建议人工复核)"
    if flag:
        print(f"  [注意] {flag}")

    # ---- 人工复核清单:把所有"机器不敢确定"的点集中列在成稿末尾,供人逐条确认 ----
    notes = []
    for sec, leaks in (("需求分析", leaks_xq), ("研究现状", leaks_xz)):
        if leaks:
            notes.append(f"- [内部指涉|{sec}] 正文残留 {leaks}:读者看不到'材料一'和 U 编号,"
                         f"请改为真实出处(作者/机构/年份)或直接删除括注。")
    for sec, sus in (("需求分析", sus_xq), ("研究现状", sus_xz)):
        for n in sus:
            notes.append(f"- [数字|{sec}] 「{n}」在来源材料中原样找不到。常见原因:单位换算"
                         f"($220K→22万美元、12M→1200万,语义正确)或模型改写(有风险),请对照原文核语义。")
    for h in hints:
        notes.append(f"- [预检] {h}")
    if not passed and last_issues:
        notes.append(f"- [评审遗留] 第 {MAX_REFLECT_ROUNDS} 轮评审点名 {len(last_issues)} 条问题,"
                     f"已按指令自动修订、但未再复审,请逐条确认改到位"
                     f"(原始记录:output/overview_review_r{MAX_REFLECT_ROUNDS}.json):")
        for it in last_issues:
            notes.append(f"    · [{it.get('lens', '')}{it.get('check', '')}|{it.get('section', '')}] "
                         f"{it.get('problem', '')}(修改指令:{it.get('fix', '')})")
    if notes:
        review_block = ("\n\n" + "=" * 30 + "\n【人工复核清单】(机器自检生成;逐条确认处理后,删除本区块再交稿)\n"
                        + "\n".join(notes) + "\n")
    else:
        review_block = ("\n\n" + "=" * 30 + "\n【人工复核清单】无待复核项:评审通过,数字全部可溯源。交稿前删除本行。\n")

    gg.dump("overview_meta", {"requirement": requirement, "review_chars": len(review),
                              "passed": passed, "rounds": rnd})
    final = f"(一)需求分析\n{xuqiu}\n\n(二)研究现状\n{xianzhuang}\n" + review_block
    out = OUT_DIR / "overview.txt"
    out.write_text(final, encoding="utf-8")
    print(f"\n  [已存盘] {out} {flag}")

    print("\n===== 概述成稿 =====\n")
    print(final)
    return {"units": units, "xuqiu": xuqiu, "xianzhuang": xianzhuang, "passed": passed}


# ================================================================== 命令行入口
def main():
    args = sys.argv[1:]
    if not args:
        print("用法: python overview_gen.py 综述.txt \"研究需求一句话\"")
        sys.exit(1)
    review_path = Path(args[0])
    if not review_path.exists():
        print(f"[错误] 找不到文件: {review_path}")
        sys.exit(1)
    review = review_path.read_text(encoding="utf-8").strip()
    requirement = args[1] if len(args) > 1 else "(未提供,请贴合综述主题)"

    print(f"综述来源: {review_path}  ({len(review)} 字)")
    print(f"研究需求: {requirement}")
    print(f"模型: {gg.MODEL}")
    gen_overview(review, requirement)


if __name__ == "__main__":
    main()
