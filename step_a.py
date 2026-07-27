# -*- coding: utf-8 -*-
"""
A 步 —— 结构化拆解:把文献综述拆成"方法单元"(units)

全链唯一被两条线共用的业务步骤:goal_gen(抽 gap 的证据源)与 overview_gen
(需求分析的痛点素材)都从这里拿 units。自带指纹缓存:同一份综述+同一套配置
只抽一次,两条线证据同源;换综述/改开关/换语言自动重抽,无需手动删缓存。

提示词按功能开关(WITH_ORIGIN/WITH_QUANT)条件拼装,所以随本站走,
不进 prompts_goal.py(那里只放静态模板)。

缓存指纹 = md5(综述全文 | origin 开关 | quant 开关 | 输出语言指令)。
语言指令取 config 原值,不受 translate_en 运行期覆盖影响——中英两套 units
不会互相冒充。

测试隔离注意:本模块从 llm_core 按名引入 OUT_DIR/call_llm,测试里改
gg.OUT_DIR 不会影响这里——要重定向缓存路径或打桩,请改本模块属性
(import step_a; step_a.OUT_DIR = ...; step_a.call_llm = ...)。
"""

import json

from llm_core import call_llm, parse_json, dump, OUT_DIR
from config import WITH_ORIGIN, WITH_QUANT, TEMP_A
from config import _OUT_LANG        # 下划线名不随 * 导出,显式引入(参与缓存指纹)


# ------------------------------------------------------------------ A 段 prompt(条件拼装)
A_SYS = (
    "你是严谨的文献分析员。只做忠实抽取和有依据的推断,绝不编造。"
    + ("数字必须如实抄录综述原文,综述没给的数值一律留空。" if WITH_QUANT else "")
)

_A_ORIGIN = ('- origin:        "国内"/"国外"/"未知"。只有综述明确点出国别/机构/作者国籍等线索时才判,'
             '线索不足写"未知",不猜。\n') if WITH_ORIGIN else ""
_A_METRICS = ('- metrics:       定量指标列表,每项含 name/value/condition/is_best_known;'
              'value 如实抄录,该方法无定量指标时输出空列表 []。\n') if WITH_QUANT else ""

A_USER = ("""把下面的研究现状综述,按方法逐条拆成"方法单元"。

严格输出一个 JSON 数组,每个元素是一个方法单元,字段:
- id:            编号,如 "U1"
- work:          方法/工作的名称或简称
""" + _A_ORIGIN + """- solves:        它解决的核心问题
- data_scene:    在什么数据、什么设定下验证
""" + _A_METRICS + """- assumption:    它依赖的关键前提
- limitation:    明说的局限 + 推断的潜在短板(推断的在文字里标 "(推断)")

规则(重要):
1. 每个方法都必须输出一个单元,不要因为信息不全就省略整个单元。
2. 字段无信息填 null。
3. 只抽综述里真实出现的内容,不得编造。
4. 同一项研究即使用了多个算法或报告多个指标,也合并成一个单元,不要拆成多条。
只输出 JSON,不要任何额外文字。

研究现状综述:
""")


# ------------------------------------------------------------------ 步骤
def _a_fingerprint(review: str) -> str:
    """A 步缓存指纹:综述内容或抽取配置(国内外/定量/输出语言)一变,缓存即失效。"""
    import hashlib
    key = f"{review}|origin={WITH_ORIGIN}|quant={WITH_QUANT}|lang={_OUT_LANG}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def step_a(review: str):
    """结构化拆解综述。goal_gen 与 overview_gen 共用:同一份综述+同一套配置只抽一次。

    units.json + units_fingerprint.txt 构成缓存;换综述/改开关/换语言会自动重抽,
    无需手动删缓存。语言在指纹里,所以中英两套 units 不会互相冒充。
    """
    print("\n===== A 结构化拆解现状 =====")
    fp = _a_fingerprint(review)
    cache, fp_file = OUT_DIR / "units.json", OUT_DIR / "units_fingerprint.txt"
    if cache.exists() and fp_file.exists() and fp_file.read_text(encoding="utf-8").strip() == fp:
        units = json.loads(cache.read_text(encoding="utf-8"))
        print(f"  综述与配置未变,复用已有 units.json({len(units)} 个单元)")
        return units
    raw = call_llm(A_SYS, A_USER + review, TEMP_A)
    units = parse_json(raw)
    print(f"  抽到 {len(units)} 个方法单元")
    dump("units", units)
    fp_file.write_text(fp, encoding="utf-8")
    return units
