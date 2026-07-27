# -*- coding: utf-8 -*-
"""
反思的负对照测试。

造 1 条干净候选 + 4 条各带一种已知缺陷,喂给 step_reflect,看它:
- 干净的 → 通过(并走到 D 扩写)
- 4 条带缺陷的 → 淘汰,且对应那一项打 1 分

跑法(在 plan_gen 目录下):
  conda activate deepsearch
  python tests\\test_reflect.py
"""

import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # tests/ → goal_gen 根
import goal_gen as gg   # 复用主流程的 step_reflect / step_d / 配置

gg.OUT_DIR = gg.OUT_DIR / "test_run"   # 测试产物隔离,不覆盖正式 output(如 research_goal.txt)
gg.OUT_DIR.mkdir(exist_ok=True)

# ------------------------------------------------------------------ 最小上下文
UNITS = [
    {"id": "U1", "work": "GRU-D", "origin": "未知", "solves": "多元时间序列缺失值插补",
     "data_scene": None, "metrics": [], "assumption": "假设数据缺失完全随机(MCAR) (推断)",
     "limitation": "顺序处理与记忆容量限制，大规模数据可扩展性差"},
    {"id": "U5", "work": "GRIN", "origin": "未知", "solves": "多元时间序列缺失值插补",
     "data_scene": None, "metrics": [], "assumption": "假设数据缺失完全随机(MCAR) (推断)",
     "limitation": "计算复杂度高，大规模场景吃力"},
    {"id": "U18", "work": "CSDI", "origin": "未知", "solves": "多元时间序列缺失值插补",
     "data_scene": None, "metrics": [], "assumption": "假设数据缺失完全随机(MCAR) (推断)",
     "limitation": "计算复杂度相当高，存在边界一致性问题"},
    {"id": "U28", "work": "GPT4TS", "origin": "未知", "solves": "多元时间序列缺失值插补",
     "data_scene": None, "metrics": [], "assumption": "假设数据缺失完全随机(MCAR) (推断)",
     "limitation": "尚处于早期探索，成熟度不足 (推断)"},
    # 一个明显跟"缺失机制"无关的单元,用来测"挂错证据"
    {"id": "U24", "work": "缺失率统计工具", "origin": "未知", "solves": "统计数据集的缺失比例",
     "data_scene": None, "metrics": [], "assumption": None,
     "limitation": "仅统计缺失比例，不涉及任何插补方法"},
]

GAPS = [
    {"gap_id": "G1", "type": "假设失效",
     "summary": "现有方法均假设缺失完全随机(MCAR)，但真实场景常为非随机缺失(MAR/MNAR)。",
     "involved_units": ["U1", "U5", "U18", "U28"],
     "tension": "现实数据缺失常依赖观测值或缺失值本身，现有方法只处理 MCAR，真实场景可靠性不足。"}
]

REQUIREMENT = "面向多元时间序列缺失值插补，提出更贴近真实场景、可扩展、可靠的深度学习插补方法"

# ------------------------------------------------------------------ 干净候选(应通过 → 走到 D)
CLEAN = {
    "gap_id": "G1",
    "objective": "开发一种能显式建模 MAR/MNAR 缺失机制的深度学习插补模型，在真实数据集上降低 RMSE。",
    "key_problems": [
        "现有方法依赖 MCAR 假设，在 MAR/MNAR 下因未建模缺失机制而性能下降",
        "需设计能捕捉缺失模式与观测值依赖关系的损失函数或注意力机制",
    ],
    "quantitative_delta": {
        "metric": "RMSE", "current_level": "需补充调研",
        "target_level": "拟定降低 15%(待可行性论证)", "increment": "从当前基线降低 RMSE 至拟定 15% 的水平"},
    "evidence_from_review": ["U1", "U5", "U18", "U28"],
    "why_not_trivial": "非随机缺失下现有方法系统性失效，需突破 MCAR 假设、建模复杂缺失机制。",
}


def variant(**overrides):
    c = json.loads(json.dumps(CLEAN, ensure_ascii=False))  # 深拷贝
    c.update(overrides)
    return c

# 4 条各带一种缺陷
D_HALLU = variant(quantitative_delta={
    "metric": "RMSE", "current_level": "当前主流方法 RMSE 基线为 0.15",  # 综述里没有,编的
    "target_level": "0.10", "increment": "从 0.15 降到 0.10"})
D_VAGUE = variant(objective="提升时间序列插补的整体效果与泛化能力。")   # 空话
D_EVID = variant(evidence_from_review=["U24"])                        # 挂了不相关的统计工具
D_INCONSIST = variant(                                                # 增量/关键问题与 MNAR 的 gap 对不上
    key_problems=["现有方法计算开销大、内存占用高", "需要并行化以提升吞吐量"],
    quantitative_delta={"metric": "吞吐量(样本/秒)", "current_level": "需补充调研",
                        "target_level": "拟定提升 50%(待可行性论证)", "increment": "吞吐量提升 50%"})

# (标签, 期望, 该缺陷对应的评分项) —— 标签不进 prompt,只用于对分
CASES = [
    (CLEAN,       "clean · 应通过",        "pass",   None),
    (D_HALLU,     "编造基线 · 应淘汰",     "reject", "no_hallucination"),
    (D_VAGUE,     "空话目标 · 应淘汰",     "reject", "specificity"),
    (D_EVID,      "挂错证据 · 应淘汰",     "reject", "evidence_relevance"),
    (D_INCONSIST, "增量不一致 · 应淘汰",   "reject", "consistency"),
]

if __name__ == "__main__":
    print(f"模型: {gg.MODEL}\n")
    cands = [c for c, _, _, _ in CASES]

    survivors = gg.step_reflect(cands, UNITS, GAPS, REQUIREMENT)

    # step_reflect 已把全部判定(按输入顺序)写进 output/reflections.json
    refl = json.loads((gg.OUT_DIR / "reflections.json").read_text(encoding="utf-8"))

    print("\n================ 负对照对分 ================")
    caught = 0
    for i, (c, label, expect, crit) in enumerate(CASES):
        v = refl[i].get("verdict", "?")
        sc = refl[i].get("scores", {})
        if expect == "pass":
            ok = v in ("通过", "标记")
        else:
            ok = (v == "淘汰")
        mark = "✓" if ok else "✗"
        detail = f"verdict={v}"
        if crit:
            detail += f", {crit}={sc.get(crit, '?')}分"
        print(f"  {mark} [{label}]  {detail}")
        if expect == "reject" and ok:
            caught += 1

    print(f"\n  抓到缺陷 {caught}/4;clean {'正确通过' if survivors else '被误杀!'}")

    # 至少让通过的(clean)走到 D,验证全链路
    if survivors:
        print("\n================ 通过反思的候选 → D 扩写 ================")
        gg.step_d(survivors, UNITS, REQUIREMENT)
    else:
        print("\n[异常] 没有候选通过反思,连 clean 都被淘汰了,说明反思过严。")
