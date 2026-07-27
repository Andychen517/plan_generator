# -*- coding: utf-8 -*-
"""
锦标赛(排序)的负对照测试 —— 锦标赛现在判"已扩写的完整目标正文"。

造 3 条已扩写目标,质量明显有别:
- STRONG:证据多、核心痛点、正文扎实 → 应排第 1
- MID:  证据一般、价值中等
- WEAK: 证据只有 1 个、空白边缘、正文空 → 应排最后

跑法(在 plan_gen 目录下):
  conda activate deepsearch
  python tests\\test_tourney.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # tests/ → goal_gen 根
import goal_gen as gg

gg.OUT_DIR = gg.OUT_DIR / "test_run"   # 测试产物隔离,不覆盖正式 output
gg.OUT_DIR.mkdir(exist_ok=True)

REQUIREMENT = "面向多元时间序列缺失值插补,提出更贴近真实场景、可扩展、可靠的深度学习插补方法"

STRONG = {
    "gap_id": "G1",
    "evidence_from_review": ["U0", "U1", "U2", "U3", "U4", "U5", "U6", "U7", "U8", "U9"],  # 证据多
    "_goal_text": (
        "本研究旨在开发一种显式建模非随机缺失(MAR/MNAR)机制的深度学习插补方法。"
        "针对 GRU-D、BRITS、CSDI、SAITS 等现有方法普遍默认数据完全随机缺失(MCAR)、"
        "在真实场景下产生系统性偏差的核心痛点,本研究拟设计能捕捉缺失机制与观测值依赖关系的"
        "新型损失函数,并在真实医疗与金融时序数据上系统验证,填补该领域空白、建立起始基线。"
    ),
}
MID = {
    "gap_id": "G2",
    "evidence_from_review": ["U0", "U3", "U4"],  # 证据一般
    "_goal_text": (
        "本研究旨在设计一种高效可扩展的插补框架,针对 RNN 顺序处理瓶颈与扩散模型的高算力问题,"
        "通过并行化或轻量化手段,在大规模场景下兼顾精度与效率。"
    ),
}
WEAK = {
    "gap_id": "G3",
    "evidence_from_review": ["U10"],  # 只有 1 个边缘证据
    "_goal_text": (
        "本研究拟探索缺失比例统计工具对插补流程的辅助作用,以期为流程提供参考。"
    ),
}

CANDS = [MID, WEAK, STRONG]   # 故意乱序,看它能不能排对

if __name__ == "__main__":
    print(f"模型: {gg.MODEL}\n")
    ranked = gg.step_tourney(CANDS, REQUIREMENT)

    print("\n================ 排序对分 ================")
    top = ranked[0].get("gap_id")
    bottom = ranked[-1].get("gap_id")
    print(f"  {'✓' if top == 'G1' else '✗'} 最强(G1)排第 1  —— 实际第 1 是 {top}")
    print(f"  {'✓' if bottom == 'G3' else '✗'} 最弱(G3)排最后 —— 实际最后是 {bottom}")
    print(f"  {'✓' if top == 'G1' and bottom == 'G3' else '✗'} 整体排序合理")

    print("\n排名:")
    for s in ranked:
        print(f"  #{s['rank']} {s['gap_id']} 总分{s.get('total')} {s.get('scores')}")
