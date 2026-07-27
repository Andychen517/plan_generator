# -*- coding: utf-8 -*-
"""
概述站的工程函数 —— 代码 tripwire(确定性检查)+ 文本清理,纯代码不调模型

precheck        主题无关预检:数字密度/两节数字重复/末段数值目标/绝对化措辞/近完美指标
check_numbers   数字溯源:成稿数字必须能在来源材料找到(只警示不拦截,交人工核)
_check_uid      内部指涉泄漏:U 编号/材料标签(材料一/二)不许出现在正文
_clean_prose    剥 r1 思维块/代码围栏/开头引导句

约定:本文件只放确定性代码检查,业务流程在 overview_gen.py,提示词在 prompts_overview.py。
"""

import re

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
_ABS_WORDS = ["无效", "彻底解决", "完全解决", "完全消除", "首个", "最优", "最先进", "监管冲突"]
_PERFECT_RE = re.compile(r"R²\s*[=≥>]\s*0\.9{2}\d*|\b(?:100|9[89](?:\.\d+)?)\s*%")
_TARGET_RE = re.compile(r"[≥≤]\s*\d|R²|\d+(?:\.\d+)?\s*%")


def precheck(xuqiu: str, xianzhuang: str) -> list:
    """主题无关的确定性检查,产出警示清单(打印,并喂给镜头3复核)。"""
    hints = []
    n_xq = len(set(_NUM_RE.findall(xuqiu)))
    if n_xq > 6:
        hints.append(f"需求分析共出现 {n_xq} 个不同数字,超过'≤5 个核心数字'的上限,疑似数据堆砌")
    both = set(_NUM_RE.findall(xuqiu)) & set(_NUM_RE.findall(xianzhuang))
    both -= {"1", "2", "3", "4", "5", "2024", "2025", "2026"}      # 常见小数字/年份不算
    if len(both) >= 3:
        hints.append(f"两节重复出现同样的数字 {sorted(both)},两节分工可能没拉开")
    paras = [p for p in xuqiu.split("\n") if p.strip()]
    if paras and _TARGET_RE.search(paras[-1]):
        hints.append("需求分析末段(研究问题)含数值/指标表述,疑似写入了拟定数值目标")
    for text, sec in ((xuqiu, "需求分析"), (xianzhuang, "研究现状")):
        found = [w for w in _ABS_WORDS if w in text]
        if found:
            hints.append(f"{sec}含绝对化措辞 {found}")
        perfect = _PERFECT_RE.findall(text)
        if perfect:
            hints.append(f"{sec}引用了接近完美的异常指标 {perfect},不宜作代表性进展")
    for h in hints:
        print(f"  [预检] {h}")
    if not hints:
        print("  [预检] 未发现问题")
    return hints


def check_numbers(prose: str, source_text: str, label: str) -> list:
    """数字溯源 tripwire:成稿里出现的数字,必须能在来源材料里找到同样的数字串。

    只警示不拦截(年份、单位换算如 $10B→100亿 可能误报,交人工核)。返回可疑数字列表。
    """
    src_nums = set(_NUM_RE.findall(source_text))
    suspects = [n for n in dict.fromkeys(_NUM_RE.findall(prose)) if n not in src_nums]
    if suspects:
        print(f"  [数字警示] {label}:以下数字在来源材料里找不到,需人工核对: {suspects}")
    else:
        print(f"  [数字核对] {label}:正文所有数字都能在来源材料里找到")
    return suspects


def _check_uid(prose: str, label: str) -> list:
    """内部指涉泄漏检查:U 编号、prompt 材料标签(材料一/二)都不许出现在正文。"""
    leaks = sorted(set(re.findall(r"U\d+", prose)))
    leaks += sorted(set(re.findall(r"材料[一二12][^,。;)()]{0,6}", prose)))
    if leaks:
        print(f"  [警告] {label} 正文残留内部指涉 {leaks}(读者看不到'材料一'和 U 编号,须改为真实出处或删除)")
    return leaks


def _clean_prose(text: str) -> str:
    """剥 r1 思维块 / 代码围栏 / 开头引导句(与 goal_gen.step_d 同款兜底)。"""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"```(?:\w+)?", "", text).strip()
    text = re.sub(r"^\s*(based on|here is|below is|the following is|好的|以下是|下面是|以下为)[^\n]*?[:：]\s*",
                  "", text, flags=re.IGNORECASE).strip()
    # 再兜一层:开头"××综述如下。/概述如下:"式引导句(生成 prompt 已禁,防漏网变体)
    text = re.sub(r"^[^\n。:：]{0,40}如下[。::]\s*", "", text).strip()
    return text
