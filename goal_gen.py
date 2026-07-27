# -*- coding: utf-8 -*-
"""
研究目标生成 —— A→B→C 三步 walking skeleton

流程:
  文献综述(现状)
    --A 结构化拆解--> units    (每个方法一条,含 国内外 + 定量指标)
    --B 对比抽 gap--> gaps     (5 类 gap,强制多样,每条挂单元)
    --C gap 转目标--> candidates(申报书级:objective + 拟解决关键问题 + 定量增量)
  --> 按成稿模板打印 2-3 条研究目标

调用方式与仓库一致:读 .env.local 的 OPENAI_KEY / OPENAI_ENDPOINT / CUSTOM_MODEL
(默认 deepseek/deepseek-r1-0528, 走 OpenRouter)。

用法:
  conda activate deepsearch
  cd E:\\ClaudeCode\\deep-research-python\\goal_gen
  python goal_gen.py
"""

import os
import re
import json
import time
from pathlib import Path

from openai import OpenAI
from prompts_goal import *          # 提示词全部集中在 prompts_goal.py

# ------------------------------------------------------------------ 配置区
REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = Path(__file__).resolve().parent / "output"
OUT_DIR.mkdir(exist_ok=True)

# 读 .env.local:先找 goal_gen 自己目录(独立分发/朋友测试),再找仓库根(原有布局)
try:
    from dotenv import load_dotenv
    for _envp in (Path(__file__).resolve().parent / ".env.local", REPO_ROOT / ".env.local"):
        if _envp.exists():
            load_dotenv(_envp)
            break
except ImportError:
    pass

MODEL = os.getenv("CUSTOM_MODEL") or "deepseek/deepseek-r1-0528"
CLIENT = OpenAI(
    api_key=os.getenv("OPENAI_KEY"),
    base_url=os.getenv("OPENAI_ENDPOINT", "https://api.openai.com/v1"),
    timeout=300,          # r1 推理慢,给足超时
    max_retries=0,        # 关掉库自带重试,用我们自己的(下面 call_llm)
)

from config import *                # 可调参数(开关/温度/上限)全部集中在 config.py
from config import _OUT_LANG        # 下划线名不随 * 导出,显式引入(参与 A 步缓存指纹)


# ------------------------------------------------------------------ 工具函数
def call_llm(system: str, user: str, temperature: float, max_retries: int = 4) -> str:
    """调 OpenRouter/自定义模型,返回文本内容。带重试:空响应或 API 报错就退避重发。"""
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = CLIENT.chat.completions.create(
                model=MODEL,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system + " " + _OUT_LANG},
                    {"role": "user", "content": user},
                ],
            )
            content = (resp.choices[0].message.content or "").strip()
            if content:
                return content
            last_err = "空响应"
        except Exception as e:                       # API/网络/网关瞬时错误
            last_err = f"{type(e).__name__}: {e}"
        if attempt < max_retries:
            wait = 3 * attempt                       # 3s, 6s, 9s 退避
            print(f"    [重试] 第 {attempt} 次失败({last_err}),{wait}s 后重发...")
            time.sleep(wait)
    raise RuntimeError(f"call_llm 连续 {max_retries} 次失败,最后一次:{last_err}")


def parse_json(text: str):
    """容错解析 —— 对付 deepseek-r1 的思维过程 / 代码块包裹。

    步骤:剥 <think>…</think> → 剥 ```json 代码块 → 直接 loads →
    失败则用括号配平提取第一个 JSON 数组/对象。
    """
    if not text:
        raise ValueError("模型返回为空")

    # 1. 去掉 r1 的思维块
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # 2. 去掉 ```json ... ``` 围栏
    text = re.sub(r"```(?:json)?", "", text).strip()

    # 3. 先直接试
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 4. 括号配平:找第一个 [ 或 {,配平到对应的收尾
    start = None
    for i, ch in enumerate(text):
        if ch in "[{":
            start = i
            open_ch, close_ch = ch, "]" if ch == "[" else "}"
            break
    if start is None:
        raise ValueError(f"没找到 JSON 结构,原文前 200 字:\n{text[:200]}")

    depth = 0
    in_str = False
    esc = False
    for j in range(start, len(text)):
        ch = text[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:j + 1])
    raise ValueError(f"JSON 括号不配平,原文前 200 字:\n{text[:200]}")


def dump(name: str, obj) -> None:
    """中间结果存盘,方便调 prompt 时对比。"""
    p = OUT_DIR / f"{name}.json"
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [已存盘] {p}")


# ------------------------------------------------------------------ A/B/C 三段 prompt
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




C_SYS = (
    "你是科研选题撰写专家。产出的研究目标必须明确、具体、准确,避免笼统,绝不编造。"
    + ("并能定量说明相对现状的增量。" if WITH_QUANT else "")
)



C_USER_MID = ("""

方法单元""" + ("(含定量指标,供你引用作证据)" if WITH_QUANT else "(供你引用作证据)") + """:
""")

_C_QUANT = ("""- quantitative_delta:   定量增量,是一个对象,子字段:
    - metric:         衡量指标(如 引用F1)。比例/倍数型指标必须写明分母与口径
                      (如"能耗比例(除冰系统输入能量/同工况热融法能耗)"),
                      阈值型指标写明操作性定义(如"初始覆冰12.5mm下的残余厚度"),
                      不许只给"能耗比例""除冰厚度"这种没定义的裸名字。
    - current_level:  当前水平,必须引用上面单元 metrics 里的真实数值并注明来自哪个单元;
                      若现状确实没有数值,填 "需补充调研",绝不编造。
    - target_level:   本项目目标值。有真实基线给具体目标并注"预期";无基线但能合理预估标"拟定 XX(待可行性论证)";
                      无基线且难以预估,留空("")或写"待确定",不必硬编数字。
    - increment:      增量表述。有基线写"从 X 提升到 Y";无基线且无拟定值可留空或"待确定"。
""" if WITH_QUANT else "")

C_USER_TAIL = ("""

把每个 gap 转成一条研究目标。
严格输出一个 JSON 数组,每个元素字段:
- gap_id:               关联的 gap
- objective:            研究目标本体。明确、具体、准确,含可衡量方向;禁止"提高效率""增强泛化性"这类空话。
                        目标声称的适用范围(如线路长度、部署规模、人群)不得超出证据单元
                        实际支持的范围:证据是 3m 试验就不要写"在 10m 时维持/确保";
                        确要外推,写成"并验证向 10m 级的外推能力(拟定,待实验论证)"。
- key_problems:         拟解决的关键问题列表,逐条详细说明。
""" + _C_QUANT + """- evidence_from_review: 支撑该目标的单元 id 列表
- why_not_trivial:      为什么这条目标不空、未被解决
只输出 JSON,不要任何额外文字。
""")


D_ONE_HEAD = ("下面是一条研究方向(JSON,含目标、拟解决的关键问题、"
              + ("定量增量、" if WITH_QUANT else "") + "证据单元):\n")

D_ONE_UNITS = """

方法单元对照表(id -> 名称/来源;正文提到某方法时用这里的名称或作者,禁止用 id):
"""

D_ONE_REQ = """

研究需求/已给假设(本目标要贴合这个方向):"""

_D_QUANT_POINT = ("""1. 用连贯散文写,自然融入三件事:本方向要做什么(目标)、拟解决的关键问题、定量增量。
   有真实基线数值的写成"从 X 提升到 Y"(数值须来自证据单元,不得编造);
   没有基线的如实写成"填补……空白""建立起始基线",不要凭空造数字。
2. 定量增量若是"拟定/预期"目标(无真实基线),正文须体现其"拟定/预期"性质,不要写成确定结论。
""" if WITH_QUANT else """1. 用连贯散文写,自然融入两件事:本方向要做什么(目标)、拟解决的关键问题。
""")

_D_N3, _D_N4 = ("3", "4") if WITH_QUANT else ("2", "3")

D_ONE_TAIL = ("""

请把这一条研究方向扩写成【一段完整的研究目标正文】,要写全、写透,不要压缩成一两句。要求:
""" + _D_QUANT_POINT + f"""{_D_N3}. 禁止"首个""首次""率先""最优""最佳"这类无依据的最高级表述,除非证据单元明确支持。
{_D_N4}. 语言具体、明确,禁止"提高效率""增强泛化性"这类空话。

【硬性要求】正文严禁出现 U1、U2 这类内部单元编号!凡提到某项现有工作,
一律改用对照表中对应的方法名称或作者(如"刘香的研究""基于 PPVT 的量表方法");
若不便点名,则概括为"现有量表方法""针对特殊儿童的方法"等自然表述。
同样严禁未经定义的数学指标或符号(如"谱半径ρ>1"这类没有上下文定义、读者无从
理解的表述):即使候选材料里有,也要改写成平实的机制描述
(如"预测结果反馈进入后续数据,形成持续放大群体差异的回路"),不得原样照抄。
只输出这一段正文本身,直接从研究目标内容开头(如"本研究旨在…" / "This research aims to…");
严禁任何前言、开场白或引导句(如"以下是…" / "Here is the…" / "Based on the provided…");
也不要 JSON、不要小标题、不要编号、不要任何 U 编号。
""")


# ------------------------------------------------------------------ 三个步骤
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


def step_b(units, n: int, requirement: str):
    print("\n===== B 对比抽 gap =====")
    units_json = json.dumps(units, ensure_ascii=False, indent=2)
    user = B_USER_HEAD + units_json + B_USER_TAIL.format(n=n, req=requirement)
    gaps = parse_json(call_llm(B_SYS, user, TEMP_B))
    if not isinstance(gaps, list):
        gaps = [gaps]
    if len(gaps) > n:                       # 硬闸:超上限直接截断
        print(f"  [硬上限] 模型给了 {len(gaps)} 个,截断到 {n} 个")
        gaps = gaps[:n]
    if not gaps:
        print("  [警告] 未抽到任何 gap:这份综述可能可提升空间很有限")
    print(f"  抽到 {len(gaps)} 个 gap")
    dump("gaps", gaps)
    return gaps


# ------------------------------------------------------------------ 去重(合并重复的 gap)




def step_dedup(gaps):
    """合并实质相同的 gap:LLM 分组+写综合 summary,代码取证据并集。"""
    if len(gaps) <= 1:
        print("\n===== 去重:gap ≤1,无需合并 =====")
        return gaps

    print("\n===== 去重:合并重复的 gap =====")
    gaps_json = json.dumps(gaps, ensure_ascii=False, indent=2)
    groups = parse_json(call_llm(DEDUP_SYS, DEDUP_HEAD + gaps_json + DEDUP_TAIL, TEMP_A))
    gaps_by_id = {g.get("gap_id"): g for g in gaps}

    merged = []
    for i, grp in enumerate(groups, 1):
        srcs = grp.get("merged_from", [])
        units = []                                   # 证据并集由代码算,保证不漏
        for gid in srcs:
            for u in gaps_by_id.get(gid, {}).get("involved_units", []):
                if u not in units:
                    units.append(u)
        merged.append({
            "gap_id": f"G{i}",
            "type": grp.get("type"),
            "summary": grp.get("summary"),
            "involved_units": units,
            "tension": grp.get("tension"),
            "merged_from": srcs,
        })

    if len(merged) < len(gaps):
        print(f"  合并:{len(gaps)} 条 → {len(merged)} 条")
        for m in merged:
            if len(m["merged_from"]) > 1:
                print(f"    {m['merged_from']} → {m['gap_id']}  (证据并集 {m['involved_units']})")
    else:
        print(f"  无重复,{len(merged)} 条原样保留")
    dump("gaps_merged", merged)
    return merged


def step_c(gaps, units, requirement: str):
    print("\n===== C gap 转研究目标 =====")
    gaps_json = json.dumps(gaps, ensure_ascii=False, indent=2)
    units_json = json.dumps(units, ensure_ascii=False, indent=2)
    user = (C_USER_HEAD + gaps_json + C_USER_REQ + requirement
            + C_USER_MID + units_json + C_USER_TAIL)
    cands = parse_json(call_llm(C_SYS, user, TEMP_C))
    print(f"  生成 {len(cands)} 条候选研究目标")
    dump("candidates", cands)
    return cands


# ------------------------------------------------------------------ 反思(逐条审查候选)

if WITH_QUANT:
    REFLECT_TAIL = """

请按以下 4 条标准逐条审查,每条打 1~3 分并给一句理由:
1. 无幻觉与语义正确:审 quantitative_delta 的 current_level 两点——
   (a) 数值能否在引用单元里找到;
   (b) 含义有没有用对:current_level 必须是 target 指标(metric)的"现状水平",
       不能把"降幅/提升量/别的指标"当成基线。
       (例:单元写"降低偏见 32%",却当成"ABROCA 基线 32%→提到 40%",这是把降幅当基线,判 2)
   没有真实基线时,看 target 是否老实标了"拟定/待论证"。
   (3=数值可溯源且语义正确,或如实留白;2=数值真但语义有偏(降幅/别的指标当基线);1=编造了基线数值)
2. 具体可证伪:objective 是否指向具体任务、含可衡量方向?(不必在句中罗列指标数值)
   (3=含可衡量方向即可;2=偏笼统,但仍指向具体任务/领域;1=纯空话,连任务方向都模糊)
3. 对齐与一致:objective 是否紧扣它的 gap?各字段方向是否一致?
   (3=紧扣 gap 且各字段一致——定量增量可只聚焦一个主指标,不必覆盖每个方面;
    2=objective↔gap 核心仍成立,只是某枝节字段有偏移,可修;
    1=objective 本身偏离了它的 gap,或字段之间直接矛盾,目标整体不成立)
4. 证据对应性:evidence_from_review 引用的单元,内容是否真跟该目标的 gap 相关、能支撑它?
   (3=都相关;2=部分不相关;1=大多不相关或牵强)

注意:不要吹毛求疵。定量增量只聚焦一个主指标、或指标名没写进 objective 句子,都不算问题,判 3;
只有实质性偏移/缺陷才判 2,硬伤才判 1。
另一条红线:objective/key_problems 中若出现未经定义的数学指标或符号(如"谱半径ρ>1"
这类没有上下文定义、申报书读者无从理解的表述),第 2 条『具体可证伪』至多判 2,
理由中写明"应改用平实的机制性语言"。
再两条红线:(a) quantitative_delta 的 metric 若是比例/倍数型却没写分母口径、或
阈值型没有操作性定义(如只写"能耗比例""除冰厚度"),第 2 条至多判 2;
(b) objective 声称的适用范围(长度/规模/人群)超出被引单元支持的范围、又没写成
"验证外推能力(拟定)"的,第 1 条『无幻觉与语义正确』至多判 2。

verdict 规则:任一条为 1 → "淘汰";没有 1 但有 2 → "标记";4 条全 3 → "通过"。

严格输出一个 JSON 对象,字段:
- gap_id:该候选的 gap_id
- scores:对象,含 no_hallucination / specificity / consistency / evidence_relevance,各 1~3 整数
- reasons:对象,同上四个键,各一句话理由
- verdict:"通过" / "标记" / "淘汰"
- reason:一句话总评
只输出 JSON,不要任何额外文字。
"""
else:
    REFLECT_TAIL = """

请按以下 3 条标准逐条审查,每条打 1~3 分并给一句理由:
1. 具体可证伪:objective 是否指向具体任务、含可衡量方向?
   (3=含可衡量方向即可;2=偏笼统,但仍指向具体任务/领域;1=纯空话,连任务方向都模糊)
2. 对齐与一致:objective 是否紧扣它的 gap?各字段方向是否一致?
   (3=紧扣 gap 且各字段一致;2=核心仍成立,只是某枝节字段有偏移,可修;
    1=objective 本身偏离了它的 gap,或字段之间直接矛盾,目标整体不成立)
3. 证据对应性:evidence_from_review 引用的单元,内容是否真跟该目标的 gap 相关、能支撑它?
   (3=都相关;2=部分不相关;1=大多不相关或牵强)

注意:不要吹毛求疵,只有实质性偏移/缺陷才判 2,硬伤才判 1。
另一条红线:objective/key_problems 中若出现未经定义的数学指标或符号(如"谱半径ρ>1"
这类没有上下文定义、申报书读者无从理解的表述),第 1 条『具体可证伪』至多判 2,
理由中写明"应改用平实的机制性语言"。
再一条红线:objective 声称的适用范围(长度/规模/人群)超出被引单元支持的范围、
又没写成"验证外推能力(拟定)"的,第 2 条『对齐与一致』至多判 2。

verdict 规则:任一条为 1 → "淘汰";没有 1 但有 2 → "标记";3 条全 3 → "通过"。

严格输出一个 JSON 对象,字段:
- gap_id:该候选的 gap_id
- scores:对象,含 specificity / consistency / evidence_relevance,各 1~3 整数
- reasons:对象,同上三个键,各一句话理由
- verdict:"通过" / "标记" / "淘汰"
- reason:一句话总评
只输出 JSON,不要任何额外文字。
"""


# 代码 tripwire 用:表"变化量"(降幅/提升量)的词——出现在 current_level 里,多半是把变化量误当基线
_DELTA_WORDS = ["reduction", "reduced", "reduce", "mitigation", "mitigat", "improvement", "improv",
                "increase", "increas", "decrease", "gain", "boost", "faster", "lower", "higher",
                "降低", "减少", "提升", "提高", "改善", "增加", "下降", "缩短", "加快", "降幅", "增幅"]


def _num_semantics_flag(cand):
    """确定性检查:current_level 含'变化量'措辞时,疑似把降幅/提升量当基线。返回警示或 None。"""
    qd = cand.get("quantitative_delta") or {}
    cur = qd.get("current_level") or ""
    if not cur or "需补充调研" in cur or "待确定" in cur:
        return None
    low = cur.lower()
    for w in _DELTA_WORDS:
        if w in low:
            return f"current_level 含「{w}」(变化量措辞),疑似把降幅/提升量当基线,需人工核语义"
    return None


def step_reflect(cands, units, gaps, requirement: str):
    """逐条审查候选:淘汰有硬伤的,保留通过/标记的(标记的挂 _verdict 供后续提示)。"""
    print("\n===== 反思:逐条审查候选 =====")
    units_by_id = {u.get("id"): u for u in units}
    gaps_by_id = {g.get("gap_id"): g for g in gaps}

    reflections, survivors = [], []
    for i, c in enumerate(cands, 1):
        cited = [units_by_id[uid] for uid in c.get("evidence_from_review", []) if uid in units_by_id]
        gap = gaps_by_id.get(c.get("gap_id"), {})
        user = (
            "待审的候选研究目标(JSON):\n" + json.dumps(c, ensure_ascii=False, indent=2)
            + "\n\n它引用的方法单元(核对证据用):\n" + json.dumps(cited, ensure_ascii=False, indent=2)
            + "\n\n它对应的研究空白 gap:\n" + json.dumps(gap, ensure_ascii=False, indent=2)
            + "\n\n研究需求/方向:" + requirement
            + REFLECT_TAIL
        )
        r = parse_json(call_llm(REFLECT_SYS, user, TEMP_A))   # 低温,判得稳
        verdict = r.get("verdict", "标记")
        if WITH_QUANT:                                         # 代码 tripwire:数值语义
            _flag = _num_semantics_flag(c)
            if _flag:
                r["semantic_warning"] = _flag
                print(f"    [语义警示] 候选{i}: {_flag}")
                if verdict == "通过":                          # LLM 放过了,硬规则至少标记
                    verdict = "标记"
                    r["verdict"] = "标记"
        reflections.append(r)
        print(f"  候选{i}({c.get('gap_id')}): {verdict} — {r.get('reason', '')}")
        if verdict != "淘汰":
            c = dict(c)
            c["_verdict"] = verdict
            survivors.append(c)

    dump("reflections", reflections)
    print(f"  通过/标记 {len(survivors)} 条,淘汰 {len(cands) - len(survivors)} 条")
    return survivors


# ------------------------------------------------------------------ 锦标赛(给候选排序)

TOURNEY_REQ = "\n\n研究需求/方向:"


def step_tourney(cands, requirement: str):
    """对已扩写的完整研究目标打分排序,只输出排名(不重排成稿)。返回排名列表。"""
    order = {c.get("gap_id"): i + 1 for i, c in enumerate(cands)}   # gap_id -> 成稿里的"研究目标X"序号
    if len(cands) <= 1:
        print("\n===== 锦标赛:目标 ≤1,无需排序 =====")
        return [{"gap_id": c.get("gap_id"), "rank": 1} for c in cands]

    print("\n===== 锦标赛:给研究目标打分排序 =====")
    items = [{"gap_id": c.get("gap_id"),
              "研究目标正文": c.get("_goal_text", ""),
              "证据单元": c.get("evidence_from_review", [])} for c in cands]
    user = (TOURNEY_HEAD + json.dumps(items, ensure_ascii=False, indent=2)
            + TOURNEY_REQ + requirement + TOURNEY_TAIL)
    scored = parse_json(call_llm(TOURNEY_SYS, user, TEMP_A))
    for s in scored:
        sc = s.get("scores", {}) or {}
        s["total"] = sc.get("evidence", 0) + sc.get("significance", 0) + sc.get("feasibility", 0)

    ranked = sorted(scored, key=lambda s: s.get("total", 0), reverse=True)
    for i, s in enumerate(ranked, 1):
        s["rank"] = i

    dump("tournament", ranked)
    print("  排名(高分在前,成稿顺序不变):")
    for s in ranked:
        pos = order.get(s.get("gap_id"))
        lab = f"研究目标{CN_NUM[pos - 1]}" if pos and pos - 1 < len(CN_NUM) else s.get("gap_id")
        print(f"    #{s['rank']} {lab}({s.get('gap_id')}) 总分{s['total']} {s.get('scores')} — {s.get('reason', '')}")
    return ranked


CN_NUM = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]


# ------------------------------------------------------------------ 互动选定(锦标赛后)
def step_pick(cands, ranked):
    """锦标赛后的互动窗口:让用户选定一个目标;make_plans.py 据此只生成该目标的方案。

    选择存 output/selected_goal.json;直接回车或非交互环境(后台/管道)则保留全部、
    并清掉上次的旧选择(避免新一轮目标配旧编号)。
    """
    import sys
    sel_path = OUT_DIR / "selected_goal.json"
    if len(cands) <= 1:
        sel_path.unlink(missing_ok=True)
        return

    rank_by_gap = {r.get("gap_id"): r for r in ranked}
    print("\n===== 选定目标(互动窗口) =====")
    for i, c in enumerate(cands, 1):
        r = rank_by_gap.get(c.get("gap_id"), {})
        lab = CN_NUM[i - 1] if i - 1 < len(CN_NUM) else str(i)
        print(f"  [{i}] 研究目标{lab}(锦标赛第 {r.get('rank', '?')} 名,总分 {r.get('total', '?')}):"
              f" {str(c.get('objective', ''))[:60]}")

    if not sys.stdin.isatty():
        sel_path.unlink(missing_ok=True)
        print("  (非交互环境,跳过选择,保留全部;要选定请在交互终端重跑,"
              "或手工写 output/selected_goal.json)")
        return

    try:
        ans = input("输入你选定的目标编号(直接回车=保留全部): ").strip()
    except EOFError:                     # isatty 误判(某些后台/管道环境)→当非交互,保留全部
        sel_path.unlink(missing_ok=True)
        print("\n  (读不到输入,按非交互处理:保留全部)")
        return
    if ans.isdigit() and 1 <= int(ans) <= len(cands):
        i = int(ans)
        c = cands[i - 1]
        sel = {"index": i, "gap_id": c.get("gap_id"), "objective": c.get("objective")}
        sel_path.write_text(json.dumps(sel, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  已选定研究目标{CN_NUM[i - 1]};make_plans.py 将只生成它的方案(plan_final.pdf)")
    else:
        sel_path.unlink(missing_ok=True)
        print("  未选定,保留全部目标(make_plans.py 将生成 plan1~N)")


def step_d(cands, units, requirement: str) -> str:
    """逐条把候选扩写成一段完整研究目标,3 个目标彼此独立、都写全。"""
    print("\n===== D 逐条扩写研究目标 =====")
    units_map = "\n".join(f"{u.get('id')} = {u.get('work')}" for u in units)

    goals = []
    for i, c in enumerate(cands, 1):
        cand_json = json.dumps(c, ensure_ascii=False, indent=2)
        user = (D_ONE_HEAD + cand_json + D_ONE_UNITS + units_map
                + D_ONE_REQ + requirement + D_ONE_TAIL)
        prose = call_llm(D_SYS, user, TEMP_C)
        prose = re.sub(r"<think>.*?</think>", "", prose, flags=re.DOTALL).strip()
        prose = re.sub(r"```(?:\w+)?", "", prose).strip()
        # 兜底:剥掉开头的引导句(如 "Here is the ...:" / "以下是……:")
        prose = re.sub(r"^\s*(based on|here is|below is|the following is|以下是|下面是|以下为)[^\n]*?[:：]\s*",
                       "", prose, flags=re.IGNORECASE).strip()
        leftover = sorted(set(re.findall(r"U\d+", prose)))
        if leftover:
            print(f"  [警告] 目标{i} 仍残留内部编号 {leftover}")
        mathy = sorted(set(re.findall(r"谱半径|spectral radius|[ρλσ]\s*[>≥<≤=]", prose)))
        if mathy:
            print(f"  [警告] 目标{i} 含未定义数学指标 {mathy},建议改为平实的机制描述")
        print(f"  目标{i} 扩写完成 ({len(prose)} 字)")
        c["_goal_text"] = prose                      # 挂上正文,供锦标赛判分
        goals.append(prose)

    parts = []
    for i, g in enumerate(goals):
        marked = cands[i].get("_verdict") == "标记"
        if LANG == "zh":
            lab = CN_NUM[i] if i < len(CN_NUM) else str(i + 1)
            head = f"研究目标{lab}"
            flag = "  ⚠ 待人工确认" if marked else ""
        else:
            head = f"Research Goal {i + 1}"
            flag = "  ⚠ needs human review" if marked else ""
        parts.append(f"{head}{flag}:\n{g}")
    final = "\n\n".join(parts)

    (OUT_DIR / "research_goal.txt").write_text(final, encoding="utf-8")
    print(f"  [已存盘] {OUT_DIR / 'research_goal.txt'}")
    return final


# ------------------------------------------------------------------ 成稿模板
def render(cand: dict) -> str:
    problems = cand.get("key_problems") or []
    problems_txt = "; ".join(problems) if isinstance(problems, list) else str(problems)
    lines = [
        f"研究目标:{cand.get('objective', '')}",
        f"  拟解决的关键问题:{problems_txt}",
    ]
    if WITH_QUANT:
        qd = cand.get("quantitative_delta") or {}
        metric = qd.get("metric") or ""
        cur = qd.get("current_level") or ""
        tgt = qd.get("target_level") or "待确定"
        inc = qd.get("increment") or "待确定"
        lines.append(f"  定量增量:针对「{cur}」的现状,将 {metric} 提升至「{tgt}」,实现「{inc}」。")
    lines.append(f"  证据单元:{cand.get('evidence_from_review', [])}")
    return "\n".join(lines)


# ------------------------------------------------------------------ 主流程
def gen_goals(review: str, n: int = N_GOALS, requirement: str = ""):
    units = step_a(review)
    gaps = step_b(units, n, requirement)
    gaps = step_dedup(gaps)                       # 去重:合并重复的 gap
    cands = step_c(gaps, units, requirement)
    cands = step_reflect(cands, units, gaps, requirement)
    if not cands:
        print("\n[警告] 所有候选都被反思淘汰,没有可成稿的目标。详见 output/reflections.json")
        return {"units": units, "gaps": gaps, "candidates": [], "goal_text": ""}

    goal_text = step_d(cands, units, requirement)     # 先扩写全部(成稿保持生成顺序)
    ranked = step_tourney(cands, requirement)         # 再对完整目标排序,只输出排名(不重排成稿)
    step_pick(cands, ranked)                          # 互动窗口:选定一个目标(可跳过)

    print("\n===== 结构化底稿(通过反思的候选) =====")
    for i, c in enumerate(cands, 1):
        flag = "  ⚠ 标记" if c.get("_verdict") == "标记" else ""
        print(f"\n[候选 {i}{flag}] {render(c)}")

    print(f"\n===== 研究目标(成稿:{len(cands)} 个独立目标) =====\n")
    print(goal_text)
    return {"units": units, "gaps": gaps, "candidates": cands, "goal_text": goal_text}


# ------------------------------------------------------------------ 玩具综述(先跑通管道用)

TOY_REQUIREMENT = "面向中文科学文献问答,做出兼顾引用准确性与实用性(低延迟/可复现)的方法。"


if __name__ == "__main__":
    import sys

    # 用法:
    #   python goal_gen.py                      -> 用内置玩具综述
    #   python goal_gen.py review.txt           -> 读 review.txt 当综述,需求用默认
    #   python goal_gen.py review.txt "研究需求..."  -> 综述 + 自定义需求
    args = sys.argv[1:]
    if args:
        review_path = Path(args[0])
        if not review_path.exists():
            print(f"[错误] 找不到文件: {review_path}")
            sys.exit(1)
        review = review_path.read_text(encoding="utf-8").strip()
        requirement = args[1] if len(args) > 1 else TOY_REQUIREMENT
        print(f"综述来源: {review_path}  ({len(review)} 字)")
    else:
        review = TOY_REVIEW
        requirement = TOY_REQUIREMENT
        print("综述来源: 内置玩具综述")

    print(f"研究需求: {requirement}")
    print(f"模型: {MODEL}")
    print(f"端点: {os.getenv('OPENAI_ENDPOINT')}")
    gen_goals(review, N_GOALS, requirement)
