# -*- coding: utf-8 -*-
"""
去重的负对照测试。

造 3 条 gap:G1 和 G3 实质相同(都是 MNAR 假设失效,措辞/证据不同),G2 独立。
喂给 step_dedup,看它:
- 把 G1、G3 合并成一组;G2 保持独立(3 条 → 2 条)
- 合并组的证据 = G1、G3 的并集

跑法(在 plan_gen 目录下):
  conda activate deepsearch
  python tests\\test_dedup.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # tests/ → goal_gen 根
import goal_gen as gg

gg.OUT_DIR = gg.OUT_DIR / "test_run"   # 测试产物隔离,不覆盖正式 output
gg.OUT_DIR.mkdir(exist_ok=True)

GAPS = [
    {"gap_id": "G1", "type": "假设失效",
     "summary": "现有方法都假设缺失完全随机(MCAR),未处理非随机缺失(MAR/MNAR)。",
     "involved_units": ["U1", "U5", "U18"],
     "tension": "真实数据常为非随机缺失,现有方法只处理 MCAR,可靠性不足。"},
    {"gap_id": "G2", "type": "能力缺口",
     "summary": "没有方法同时实现高效可扩展与高精度插补。",
     "involved_units": ["U1", "U2", "U18"],
     "tension": "RNN 顺序处理、扩散模型算力大,大规模场景可扩展性差。"},
    {"gap_id": "G3", "type": "假设失效",   # 与 G1 实质相同,只是换了说法、证据部分不同
     "summary": "现有插补模型在非随机缺失(MNAR)场景下不可靠,因其默认随机缺失前提。",
     "involved_units": ["U1", "U11", "U28"],
     "tension": "缺失依赖于未观测值时(MNAR),现有方法系统性失效。"},
]
# 期望:G1、G3 合并;G2 独立。合并后并集 = {U1,U5,U18,U11,U28}

if __name__ == "__main__":
    print(f"模型: {gg.MODEL}\n")
    merged = gg.step_dedup(GAPS)

    print("\n================ 去重对分 ================")
    ok_count = (len(merged) == 2)
    print(f"  {'✓' if ok_count else '✗'} 数量:{len(GAPS)} → {len(merged)}(期望 2)")

    mnar_group = next((m for m in merged if set(m["merged_from"]) == {"G1", "G3"}), None)
    print(f"  {'✓' if mnar_group else '✗'} G1、G3 合并到同一组")

    if mnar_group:
        got = set(mnar_group["involved_units"])
        exp = {"U1", "U5", "U18", "U11", "U28"}
        print(f"  {'✓' if got == exp else '✗'} 证据并集:{sorted(got)}(期望 {sorted(exp)})")

    g2_alone = any(m["merged_from"] == ["G2"] for m in merged)
    print(f"  {'✓' if g2_alone else '✗'} G2 保持独立")

    print("\n合并后的 gaps:")
    for m in merged:
        print(f"  [{m['gap_id']}] merged_from={m['merged_from']}  units={m['involved_units']}")
        print(f"       {m['summary']}")
