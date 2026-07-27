# -*- coding: utf-8 -*-
"""
研究方案生成(design_gen) —— 把"选定的那一个研究目标"展开成申报书的研究方案一节

对齐申报书要求:围绕如何全面有效实现项目目标,做研究分解、明确具体研究内容、
突出技术途径比较优势、论证实现可行性;并说明研究思路与方法。

四节输出(标题用短形式,2026-07-23 定):
  (一)研究内容:把目标分解成 2~4 个子研究内容,每个都"坐实"成可做的东西
  (二)思路方法:每个子内容的对象/数据→技术手段→可验证产出,连成研究方案
  (三)比较优势:每个子内容的备选路线两两对照,说明为何选定这条
  (四)可行性:理论(现状有基础)/技术(units 基线与方法成熟度)/条件(团队设备数据)

核心:"坐实"四要素(参考 Robin 把致病机制坐实成可测的体外模型)——
  ① 研究对象/数据(在什么数据、什么场景做)
  ② 技术手段(具体到方法名,不是"用深度学习")
  ③ 可验证产出(做出来长什么样、拿什么指标判断成没成;数字标"拟定/待论证")
  ④ 依托基础(拿 units 里哪个现有方法当基线/对照)
四要素齐 = 从"方向"变成"研究内容";说不清就是空话,反思打回。

步骤零·领域画像(2026-07-23 加):动笔前先识别课题领域,产出该领域的措辞与验证
惯例(design_domain.json),钉子/分解/扩写/评审全程遵循——治"示例锚定"
(上一个课题的示范词汇渗漏进下一个课题)。画像须人工确认,非交互自动采纳并进复核清单。

步骤一·钉子与维度分类(2026-07-24 改):对每个技术维度做三测试分类(干预/条件因子/
测量协议/待人工),代码按真值表(_derive_plan)推出模式与实验骨架;实验设计从固定的
"2^k 消融"升级为"试验块清单"(因子对照/多水平因素/寿命循环三种块型),消融=全干预
维度时的退化特例——治"条件因子被硬套成开关机制"的模板错配。

运行条件(重要):必须先在 goal_gen 或 make_plans 里选定了唯一一个研究目标
(output/selected_goal.json 存在)。没选定直接退出,不猜。

团队/设备/数据(条件可行):可选。传一个 txt 进来就写进"条件可行";不传就留空标"待补充"。

用法(在 plan_gen 目录下):
  python design\\design_gen.py                 # 条件可行留空
  python design\\design_gen.py team.txt        # 额外喂团队/设备/数据材料
"""

import re
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import goal_gen as gg          # 复用 call_llm / parse_json / dump / OUT_DIR / CN_NUM

# 全链固定中文出稿(英文版由 translate_en.py 翻译成稿),直接沿用 goal_gen 的语言指令

OUT_DIR = gg.OUT_DIR
TEMP = 0.4


def _llm(system, user, temperature):
    return gg.call_llm(system, user, temperature, max_retries=8)


def _clean(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"```(?:\w+)?", "", text).strip()
    text = re.sub(r"^\s*(based on|here is|below is|好的|以下是|下面是|以下为)[^\n]*?[:：]\s*",
                  "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^[^\n。:：]{0,40}如下[。::]\s*", "", text).strip()
    # 修订步(r1)爱加的杂质:开头"### 修订后的…"标题、末尾"### 修订说明"整段——从
    # "(一)研究内容"截起,砍掉"修订/修改说明"及之后,再剥每行行首的 markdown 井号
    m = re.search(r"[(（]\s*一\s*[)）]\s*研究内容", text)
    if m:
        text = text[m.start():]
    text = re.split(r"\n\s*#*\s*(?:修订说明|修改说明|说明[:：])", text)[0].strip()
    text = re.sub(r"(?m)^\s*#+\s*", "", text).strip()
    text = text.replace("**", "")          # 正文里的 markdown 粗体星号一律剥掉
    return text


# ================================================================== 读选定目标
def load_selected():
    """读 output/selected_goal.json,取回选定目标的正文 + 结构化底稿 + 证据单元。"""
    sel_p = OUT_DIR / "selected_goal.json"
    if not sel_p.exists():
        print("[未选定] 没找到 output/selected_goal.json。")
        print("  请先跑 goal_gen(结尾按编号选一个),或跑 make_plans.py 时选定,再运行本脚本。")
        sys.exit(1)
    sel = json.loads(sel_p.read_text(encoding="utf-8"))
    idx = sel.get("index")
    if not isinstance(idx, int):
        print("[异常] selected_goal.json 里没有有效的 index。")
        sys.exit(1)

    # 正文:research_goal.txt 按"研究目标X"切段,取第 idx 段(成稿顺序 = 选定编号定义处)
    goal_raw = (OUT_DIR / "research_goal.txt").read_text(encoding="utf-8")
    segs = re.split(r"研究目标[一二三四五六七八九十]( {2}⚠ 待人工确认)?[::]\s*\n", goal_raw)
    bodies = [segs[i].strip() for i in range(2, len(segs), 2)]
    if not (1 <= idx <= len(bodies)):
        print(f"[异常] 选定编号 {idx} 超出 research_goal.txt 的 {len(bodies)} 个目标。")
        sys.exit(1)
    goal_text = bodies[idx - 1]

    # 结构化底稿:candidates.json 数量与成稿一致时按 idx 对接,否则降级(只用正文)
    cands = json.loads((OUT_DIR / "candidates.json").read_text(encoding="utf-8"))
    cand = cands[idx - 1] if len(cands) == len(bodies) else {}
    if not cand:
        print("  [提示] candidates.json 与成稿数量不一致(可能有候选被反思淘汰),"
              "结构化字段降级,仅用目标正文 + 全部 units 生成。")

    # 精准溯源指针:该目标引用了哪些方法单元(evidence + key_problems 里的 U 编号并集)
    cited_ids = list(cand.get("evidence_from_review", []) or [])
    for kp in cand.get("key_problems", []) or []:
        cited_ids += re.findall(r"U\d+", kp if isinstance(kp, str) else str(kp))
    cited_ids = list(dict.fromkeys(cited_ids))          # 去重保序
    return idx, goal_text, cand, cited_ids


def load_units():
    p = OUT_DIR / "units.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


# ================================================================== 步骤零:领域画像
DOMAIN_SYS = (
    "你是科研方法专家,熟悉各学科领域的研究惯例与论文写作习惯。"
    "任务:识别研究目标所属的领域,产出该领域的'领域画像'(表述与验证惯例),"
    "供后续把目标展开成研究方案时遵循。只依据给定材料判断,不编造;"
    "线索不足的字段老实写'待人工确认'。"
)

DOMAIN_USER = """选定的研究目标(正文):
{goal_text}

该目标引用的方法单元(它们在什么数据/平台上做过验证,反映了本领域的真实做法):
{cited}

研究需求/方向:{req}

请识别这个课题所属的领域,并产出一份"领域画像"。后续所有生成步骤将照它
选词、选验证手段。全部判断只用一条统一标准:
**这个说法/这种做法,在该领域的论文里是否自然出现。**

严格输出一个 JSON 对象,字段:
- field:领域一句话(学科方向+课题类型;交叉领域要点明以哪边为主)
- reason:判断依据一句话,须指出来自目标正文或引用单元的具体线索
- verification_methods:字符串数组(至多4条)。该领域论文里验收研究成果的标准手段,
  按常用程度排;每条具体到可直接写进"可行性论证",严禁"视情况而定"这类空话
- vocabulary:对象,两个键:
  - use:字符串数组(至多8条)。该领域描述 数据/平台/研究对象/指标 时的自然用语
  - avoid:字符串数组(0~8条,**宁缺毋滥**)。只列真有串味风险的词:其他领域常用、
    但写进本领域论文会显得外行的;每条附本领域的替换说法,格式"外行词→本领域说法"。
    **严禁凑数**——本领域论文里本来就自然出现的词一律不得列入(用上面那条统一标准
    逐词自查);没有真正的外行词就给空数组
- compatibility:数组,对应研究目标包含的每个技术维度,每项含:
  - dimension:维度名
  - constraint:该维度的常用技术手段对"作用对象"的硬性要求一句话
    (哪类手段只适用于哪类载体;没有硬性要求就写"无")
- simulation:一句话。在团队/设备等真实条件未定时,该领域惯用的替代验证方案

硬规则:
- 任何字段值严禁出现 U 编号;
- verification_methods 与 simulation 只写手段的**类型与做法**(如"在该领域的公开
  数据/标准试验环境中做模拟验证"这类表述),**给定材料之外的具体数据集/平台/工具名
  一律不得出现**——具体选型是立项后调研的事,写进画像会被下游误当成既定事实;
- 判断线索不足时对应字段写"待人工确认",严禁编造行规;
- 中文为主,专有名词可保留英文原名;
- 只输出 JSON,不要任何额外文字。
"""


def _domain_block(prof):
    """画像压成注入下游 prompt 的紧凑 JSON(剔除 reason/auto_accepted 等元字段)。"""
    keep = {k: prof.get(k) for k in
            ("field", "verification_methods", "vocabulary", "compatibility", "simulation")
            if prof.get(k)}
    return json.dumps(keep, ensure_ascii=False, indent=1)


def step_domain(goal_text, cited, req):
    """步骤零:识别课题领域→产出领域画像(措辞/验证手段/兼容约束)→人工确认。

    治"示例锚定":领域知识由模型对着眼前课题现推,不再写死在 prompt 示范里。
    """
    print("\n===== 零 领域画像(提议→人工确认) =====")
    user = DOMAIN_USER.format(goal_text=goal_text,
                              cited=json.dumps(cited, ensure_ascii=False, indent=2), req=req)
    prof = gg.parse_json(_llm(DOMAIN_SYS, user, gg.TEMP_A))
    if isinstance(prof, list):
        prof = prof[0] if prof else {}
    voc = prof.get("vocabulary") or {}
    print(f"  领域判断: {prof.get('field')} — {prof.get('reason', '')}")
    print(f"  验证手段: {'、'.join(prof.get('verification_methods') or []) or '(未给出)'}")
    print(f"  自然用语: {'、'.join(voc.get('use') or []) or '(未给出)'}")
    print(f"  外行词替换: {'、'.join(voc.get('avoid') or []) or '(未给出)'}")
    for c in prof.get("compatibility") or []:
        print(f"  兼容约束·{c.get('dimension')}: {c.get('constraint')}")
    print(f"  替代验证: {prof.get('simulation', '(未给出)')}")

    auto = not sys.stdin.isatty()
    if not auto:
        try:
            ans = input("回车=接受画像;或输入正确的领域一句话替换 field"
                        "(其余字段可改 output/design_domain.json 后重跑): ").strip()
            if ans:
                prof["field"] = ans
                print(f"  领域判断已改为: {ans}")
        except EOFError:                       # isatty 误判(后台/管道环境)→当非交互
            auto = True
    if auto:
        print("  (非交互环境:自动采纳画像;领域判断请事后在复核清单确认)")
    prof["auto_accepted"] = auto
    gg.dump("design_domain", prof)
    return prof


# ================================================================== 步骤一:钉子提议 + 人工确认
PINS_SYS = (
    "你是研究方案架构师与实验设计专家。对研究目标的技术维度逐一做分类测试,"
    "并提出三颗钉子。只依据给定材料,不编造;分类必须真的跑测试而非望文生义,"
    "钉子必须具体、可实现、与被引用单元兼容。"
)

PINS_USER = """选定的研究目标(正文):
{goal_text}

被本目标引用的方法单元(钉子的依据,主数据只能取自这里的 data_scene):
{cited}

研究需求/方向:{req}

本课题的【领域画像】(表述、选型与验证手段的依据,全程遵循):
{domain}

请做三件事:

一、维度分类(为实验设计定型):先列出该目标包含的技术维度(按建议的研究顺序排),
再对每个维度依次做以下测试,按**第一个通过的测试**确定 type:
- 测试1【干预】:它是研究者施加给载体的改动吗?——能否在同一载体上做出"带它"和
  "不带它"两个版本,进行有/无对照?能 → type="干预"。
- 测试2【条件因子】:它是研究对象或环境自带的属性吗?——研究者并不发明它,只是
  选择在它的哪些取值下做测量?是 → type="条件因子",并给出 levels(取值只能来自
  给定材料;材料没提供的写"水平待调研确定",严禁编造)。
- 测试3【测量协议】:它改变的既不是载体、也不是测量对象,而是"怎么测、怎么评"?
  是 → type="测量协议"(不进实验因子表,写进测量方法)。
- 三个测试都不通过、或有两个都像 → type="待人工",在 evidence 里写一句难判在哪,
  不许硬归类。
每个维度附 evidence:一句话写明它通过了哪个测试、依据材料里的什么信息。
若一个维度名实际混着两种性质的东西,先拆成两条再分别分类。

二、单独回答 longevity:研究目标是否含长期性/耐久性/可靠性验证要求?
required 为 true 时 evidence 须引目标正文的原话;没有此类要求就 false。

三、提出三颗钉子(pins):
- core_task:一个核心任务,一句话,所有研究内容都为它服务;
- base_model:一个具体、可实现的基准载体,所有干预型维度的机制都施加在它上面;
  **必须能同时承载全部干预维度的主流机制**——逐维度自查兼容性
  (量化/剪枝/蒸馏类手段要求神经网络,随机森林/GBM 等树模型不适用;其他机制同理);
- main_data:一套主数据,**只能取自被引用单元的 data_scene**;单元里没有合适的就写
  "拟采用<某类>数据(具体来源待调研确定)",严禁编造名称。

钉子与分类的措辞硬规则:
- 所有字段值**严禁出现 U 编号**(U1、U7 等内部编号读者看不到,引用某单元的信息时
  改用该方法/装置的名称);
- 措辞与选型遵循上方【领域画像】:只用 vocabulary.use 的说法,avoid 所列外行词
  一律不得出现;base_model/main_data 的类型须满足 compatibility 的约束。

严格输出一个 JSON 对象,字段:
- dimensions:数组,每项含 name / type("干预"/"条件因子"/"测量协议"/"待人工") /
  evidence(一句话) / levels(仅条件因子需要,字符串数组)
- longevity:对象,含 required(true/false) / evidence(字符串,可空)
- pins:对象,含 core_task / base_model / main_data
- reason:一句话,分类与钉子的总体依据
只输出 JSON,不要任何额外文字。
"""


def _derive_plan(dims, longevity):
    """真值表:从维度分类机械推出 (mode, 实验骨架文本, 警示列表)。纯代码,不经模型。

    干预≥2 或 干预+条件混合 → unified(骨架=因子对照块[+每条件一个多水平块][+寿命块]);
    仅条件 → unified(单个多水平块);单干预无条件 → linear;分类失败/无要素 → linear+待人工。
    """
    itv = [d for d in dims if d.get("type") == "干预"]
    cond = [d for d in dims if d.get("type") == "条件因子"]
    proto = [d for d in dims if d.get("type") == "测量协议"]
    unknown = [d for d in dims if d.get("type") not in ("干预", "条件因子", "测量协议")]
    if unknown:
        names = [d.get("name") for d in unknown]
        return "linear", "", [f"维度 {names} 分类失败(待人工),实验设计整体待人工确认,已降级走线性叙事"]

    blocks = []
    if len(itv) >= 2 and not cond:
        blocks.append("因子对照试验:干预因子=" + "、".join(d.get("name", "?") for d in itv)
                      + "(全部为开/关两水平→configs 列全 2^k 种配置,分主实验/补充两档)")
    elif itv and cond:
        blocks.append("因子对照试验:干预因子=" + "、".join(d.get("name", "?") for d in itv)
                      + ";可按研究需要附加相关工况/环境条件列")
        for c in cond:
            lv = "、".join(c.get("levels") or []) or "水平待调研确定"
            blocks.append(f"多水平因素试验:条件因子={c.get('name', '?')}(水平:{lv});"
                          f"建议附干预列以估交互")
    elif cond:
        lv = ";".join(f"{c.get('name', '?')}(水平:{'、'.join(c.get('levels') or []) or '待调研'})"
                      for c in cond)
        blocks.append(f"多水平因素试验:条件因子={lv}(观察性比较,无干预)")
    elif len(itv) == 1:
        return "linear", "", []          # 单方向课题:线性叙事,无需骨架
    else:
        return "linear", "", ["未识别出干预或条件因子,实验设计待人工确认,已降级走线性叙事"]

    if (longevity or {}).get("required"):
        blocks.append("寿命循环试验:对象=前序试验的优选配置;追踪性能随循环/时间的衰减、"
                      "故障与维护间隔(循环规模标拟定)")
    lines = [f"- 块{i} {b}" for i, b in enumerate(blocks, 1)]
    if proto:
        lines.append("(测量协议类维度:" + "、".join(d.get("name", "?") for d in proto)
                     + "——不作因子,写进各试验块的测量方法)")
    return "unified", "\n".join(lines), []


def step_pins(goal_text, cited, req, domain):
    """模型做 维度分类+longevity+三颗钉子 → 代码按真值表推 模式+实验骨架 → 人工确认。"""
    print("\n===== 一 钉子与维度分类(提议→人工确认) =====")
    user = PINS_USER.format(goal_text=goal_text,
                            cited=json.dumps(cited, ensure_ascii=False, indent=2), req=req,
                            domain=domain)
    prop = gg.parse_json(_llm(PINS_SYS, user, gg.TEMP_A))
    pins = prop.get("pins") or {}
    dims = prop.get("dimensions") or []
    # 兼容兜底:模型退化输出字符串数组时,包装成"待人工"分类
    dims = [{"name": d, "type": "待人工", "evidence": "模型未给出分类"} if isinstance(d, str)
            else d for d in dims]
    longevity = prop.get("longevity") or {}

    print(f"  依据: {prop.get('reason', '')}")
    for i, d in enumerate(dims, 1):
        lv = f"  水平:{'、'.join(d.get('levels') or [])}" if d.get("type") == "条件因子" else ""
        print(f"  维度{i} [{d.get('type')}] {d.get('name')}{lv} — {d.get('evidence', '')}")
    print(f"  长期性要求: {'有' if longevity.get('required') else '无'}"
          + (f"({longevity.get('evidence', '')})" if longevity.get("required") else ""))

    mode, skeleton, plan_warns = _derive_plan(dims, longevity)
    print(f"  推出模式: {'统一框架' if mode == 'unified' else '线性'}(由分类真值表机械推出)")
    if skeleton:
        print("  实验骨架:")
        for line in skeleton.splitlines():
            print("    " + line)
    for w in plan_warns:
        print(f"  [警示] {w}")
    print(f"  钉子提议: 核心任务={pins.get('core_task')}")
    print(f"            基准载体={pins.get('base_model')}")
    print(f"            主数据  ={pins.get('main_data')}")

    auto = not sys.stdin.isatty()
    if not auto:
        try:
            ans = input("回车=全部接受;u=强制统一框架/l=强制线性/c=逐条改维度分类: ").strip().lower()
            if ans == "c":
                for i, d in enumerate(dims, 1):
                    new = input(f"  维度{i} {d.get('name')} 类型[{d.get('type')}] "
                                f"回车=接受,或输入新类型(干预/条件因子/测量协议/待人工): ").strip()
                    if new:
                        d["type"] = new
                mode, skeleton, plan_warns = _derive_plan(dims, longevity)
                print(f"  重推模式: {'统一框架' if mode == 'unified' else '线性'}")
                if skeleton:
                    print("  重推骨架:")
                    for line in skeleton.splitlines():
                        print("    " + line)
            elif ans == "u":
                mode = "unified"
            elif ans == "l":
                mode = "linear"
            if mode == "unified":
                for key, label in (("core_task", "核心任务"), ("base_model", "基准载体"),
                                   ("main_data", "主数据")):
                    cur = pins.get(key, "")
                    new = input(f"  {label} [{cur}] 回车=接受,或输入替换: ").strip()
                    if new:
                        pins[key] = new
        except EOFError:                       # isatty 误判(某些后台/管道环境)→当非交互
            auto = True
    if auto:
        print("  (非交互环境:自动采纳分类/骨架/钉子;请事后在复核清单确认)")

    record = {"mode": mode, "dimensions": dims, "longevity": longevity, "pins": pins,
              "skeleton": skeleton, "derive_warns": plan_warns, "auto_accepted": auto,
              "reason": prop.get("reason", "")}
    gg.dump("design_pins", record)
    return mode, pins, dims, longevity, skeleton, plan_warns, auto


# ================================================================== 步骤一:分解并坐实
DECOMP_SYS = (
    "你是国家级项目申报书的研究方案撰写专家。把一条研究目标分解成若干具体、可执行的"
    "子研究内容,每一条都必须'坐实'成可做的东西,绝不空泛,绝不编造数字。"
)

DECOMP_USER = """选定的研究目标(正文):
{goal_text}

该目标的结构化底稿(可能为空):
{cand}

【被本目标引用的方法单元】(cited)——研究对象/数据/基线数值只能取自这里:
{cited}

【其余方法单元】——仅供技术路线比较时作备选参照,不得当作本目标的研究对象或基线:
{others}

研究需求/方向:{req}

本课题的【领域画像】(表述、选型与验证手段的依据,全文遵循;
avoid 所列外行词严禁出现,技术手段与作用对象的搭配须满足 compatibility):
{domain}

请把这条研究目标分解成 2~4 个子研究内容。每个子研究内容都必须"坐实"——凑齐以下四要素,
说不清任何一条就说明该子内容还是空话、不要输出它:
① object_data:研究对象/数据/场景。**只能取自上面"被引用单元"的 data_scene 字段**
   (那是这些方法真实验证过的数据);被引用单元没写具体数据的,写"拟采用<某类>数据
   (具体数据集待调研确定)",严禁凭空编造数据集名称,也不得挪用"其余单元"里的数据。
   【技术对象要具体且匹配】object_data 或后面的技术手段涉及模型时,要指明作用在
   **什么具体载体**上(写出具体、可实现的模型/装置类别),不要笼统写
   大类名;且技术手段要与该载体兼容(如 INT8 量化只适用神经网络,不能说
   "量化随机森林/GBM")。
② tech_options:2~3 条备选技术路线,每条含
   - route:技术路线名(具体方法,不是"用深度学习"这种笼统词)
   - from_units:该路线借鉴/对比的方法单元 id(可用全部单元,但必须是真实存在的 id)
   - strength:优点
   - weakness:短板/代价(**每条都必须写,不许只写优点;选定路线自身的代价也要如实列**)
   【手段必须真解决它声称的问题】某维度用的技术,必须是真能解决该维度问题的机制:
   隐私保护必须用真正的隐私机制(差分隐私/安全聚合/加密),**联邦学习、通信压缩只是
   分布式训练架构与提效手段,不算隐私机制,不能拿来充当隐私方案**;要用联邦学习时,
   须写明"以联邦学习为训练架构、另结合差分隐私/安全聚合提供隐私保障"。
③ chosen:从 tech_options 里选定一条(写 route 名)
   advantage:选定它的比较优势(相对其他备选强在哪,要具体、有依据;写机制原理带来的
   内在特性差异,不写待实验验证的效果数值/程度)
④ verifiable_output:可验证产出——做出来长什么样、用什么指标判断成没成。
   现状基线数值**只能引用 base_units(即被引用单元)metrics 里的真实值**,并用该单元的
   方法名称指代(如"以〈该方法名称〉的…为基线"),**严禁写 U 编号**,也严禁把 tech_options
   里用于比较的其他单元(如未被引用的路线)的数字拿来当基线。
   【别人的数字≠你的基线】被引用单元里那些来自特定研究/特定群体的数字,
   只能当"问题背景",**不能直接当本项目的实验基线**;本项目基线一律写成
   "在所选数据上先测量、建立本项目基线",目标写成"相对本项目基线改善拟定 X%"。
   【指标要相对、可测】性能指标优先用相对量("相对基线降低拟定 X%"),避免拍脑袋的
   绝对阈值;确需绝对值,必须注明测量条件(什么设备/批量/环境),否则改相对。
   隐私维度不能只测延迟,要含隐私强度指标(如差分隐私预算 ε、成员推断攻击 AUC)。
   本项目目标值一律标"拟定/预期/待论证",绝不编造。
⑤ base_units:依托的现有方法单元 id(当基线/对照,**只能从被引用单元里选**)

严格输出一个 JSON 数组,每个元素含:
name / object_data / tech_options(数组) / chosen / advantage / verifiable_output / base_units(数组)
只输出 JSON,不要任何额外文字。
"""


def step_decompose(goal_text, cand, cited, others, req, domain):
    print("\n===== 二 分解并坐实子研究内容 =====")
    user = DECOMP_USER.format(
        goal_text=goal_text,
        cand=json.dumps(cand, ensure_ascii=False, indent=2) if cand else "(无,仅用正文)",
        cited=json.dumps(cited, ensure_ascii=False, indent=2),
        others=json.dumps(others, ensure_ascii=False, indent=2) if others else "(无)",
        req=req, domain=domain)
    items = gg.parse_json(_llm(DECOMP_SYS, user, TEMP))
    if not isinstance(items, list):
        items = [items]
    print(f"  分解出 {len(items)} 个子研究内容")
    for it in items:
        miss = [k for k in ("object_data", "tech_options", "chosen", "verifiable_output")
                if not it.get(k)]
        tag = f"  ⚠ 缺{miss}" if miss else "  ✓ 四要素齐"
        print(f"    · {it.get('name', '?')}{tag}")
    gg.dump("design_items", items)
    return items


# ================================================================== 步骤一B:统一框架分解
DECOMP_UNI_SYS = (
    "你是国家级项目申报书的研究方案架构师。把一条多维度研究目标组织成'统一框架'的"
    "结构化底稿:一个载体上逐层集成机制、研究相互作用。绝不空泛,绝不编造数字。"
)

DECOMP_UNI_USER = """选定的研究目标(正文):
{goal_text}

已由人确认的三颗钉子(必须原样采用,不得更换):
核心任务:{core_task}
基准模型:{base_model}
主数据:{main_data}
技术维度(按集成顺序):{dims}

实验骨架(由维度分类机械推出,experiments 必须按此骨架组块,不得增删块型):
{skeleton}

【被本目标引用的方法单元】(cited)——数据/现状基线只能取自这里:
{cited}

【其余方法单元】——仅供技术路线比较时作备选参照:
{others}

研究需求/方向:{req}

本课题的【领域画像】(表述、选型与验证手段的依据,全文遵循):
{domain}

请产出统一框架的结构化底稿。严格输出一个 JSON 对象,四个字段:

- build(内容1·构建基准):
  task / model / data 照抄三颗钉子;baseline_metrics:在主数据上训练基准模型后
  要测量的指标名列表(覆盖性能与各维度,如 准确率/CPU推理延迟/群体公平差异;
  只给指标名,不填数值——数值是立项后实验测出来的,本项目基线=届时的测量结果)。
  【基线指标必须是基准模型上真实可测的】某机制引入前不存在的指标(如未加隐私机制
  就没有"隐私保护延迟")不得列入基线;这类机制的代价一律写成"机制引入后相对基线的
  额外开销"。
  【指标用标准术语】指标名用领域标准术语(如 AUC、Equal Opportunity Difference、
  各群体假阳性率);自造名称(如"偏见比例")必须附一句明确定义(是哪两个量之比);
  公平类维度要"主优化指标+稳健性指标"多报,防止单一比例掩盖问题。
  【比例要分母,阈值要口径】比例/倍数型指标必须写明分母与测量口径
  (如"能耗比例=单次除冰系统输入能量 / 同工况传统方法能耗",不能光写"能耗比例≤1%");
  阈值型指标必须写明操作性定义与测量条件(如"初始覆冰厚度12.5mm条件下的残余厚度/
  除冰率",不能写"确保12.5mm除冰厚度"这种多义表述);与现有方法对比时,双方必须
  用同一个分母,否则不可比。

- layers(内容2·机制集成):数组,**只收录类型为"干预"的维度**,按集成顺序排,每层含:
  dimension(维度名) / mechanism(选定机制,具体方法名,**必须与基准模型兼容**,
  如 INT8 量化只适用神经网络) / tech_options(2~3条备选:route/from_units/strength/
  weakness,weakness 每条必写,选定路线的代价也如实列) / advantage(选定理由:
  写机制原理带来的内在特性差异,不写待实验验证的效果数值/程度) /
  integrate(这一机制怎么加到同一个基准模型上,一句话)。
  条件因子不作"层"——它们进 experiments 的因子列;测量协议类维度也不作层,
  写进 experiments 的测量方法。
  【手段必须真解决它声称的问题】隐私维度必须用真正的隐私机制(差分隐私/安全聚合/加密);
  联邦学习、通信压缩只是架构与提效手段,不算隐私机制;若用联邦学习须写明另配隐私机制。

- interactions(内容3·相互作用):数组,覆盖有研究价值的 干预×干预 与 干预×条件因子
  组合,每项含:
  between(两个维度名) / hypothesis(可能的相互影响,平实语言) /
  metric(用什么指标量出这个影响)。
  硬规则【交互有归宿】:声称的每组相互作用,必须能被 experiments 里的某个试验块
  估计(两个因子出现在同一块里);安排不进任何块的,不要声称。

- experiments(实验设计——这是"设计"不是数据):数组,**按上方实验骨架逐块产出,
  不得增删块型**;每块含 id / type("因子对照试验"/"多水平因素试验"/"寿命循环试验") /
  name / answers(该块回答哪些效应:主效应/交互,与 interactions 呼应) /
  metrics(统一测量的指标集,与 baseline_metrics 一致;含隐私类机制时,强度指标
  写明保护粒度是样本级还是用户级)。按块类型另附:
  · 因子表类(因子对照试验/多水平因素试验):factors 数组,每因子含 name /
    kind("干预"/"条件") / levels(条件因子的水平只能取自给定材料,没有就写
    "水平待调研确定",严禁编造)。**全部因子均为二元干预时**,configs 必须列全
    2^k 种配置(缺任何一组,某对交互就算不出来);资源有限不许缺组,只许标
    "主实验/补充"两档优先级。差值分析用**多背景差值族**刻画某因子的总体效果
    (多个配置差共同反映),不得只用一对相邻配置代表它。
  · 寿命循环类:object(试验对象,通常为前序块的优选配置) / cycles(循环规模,
    标"拟定") / tracked(追踪量列表:性能衰减、故障、维护间隔等)。
  goal:拟定的相对目标一句话(绝不写具体数值)。

- 硬规则【尺度/范围一致性】:目标声称的应用范围(线路长度、部署规模、覆盖人群等)
  若超出主数据实际支持的范围(如数据来自 3 米试验、目标却写 10 米线路),**不得**写成
  "确保在<目标范围>达成";必须写成分级外推路径:"先在主数据范围内校准模型,再经
  <中间尺度>仿真或实验逐级验证外推能力,最终在<目标范围>验证"。范围一致时不受此限。

- 硬规则【优点不得无代价断言】:tech_options 的 strength 和 advantage 不得写成
  绝对化的免费午餐(如"不增加额外能耗""不影响精度");要写成条件化、可验证的表述
  (如"在总输入能量受控的条件下,提高远端能量利用率")。

- 硬规则【措辞贴合领域】:全文遵循上方【领域画像】——只用 vocabulary.use 的说法,
  avoid 所列外行词一律不得出现;各层 mechanism 与基准载体的搭配须满足
  compatibility 约束。判断标准仍是:这个词在该领域的论文里是否自然出现。

- 另一条硬规则【场景约束↔机制对应】:研究需求/目标里渲染的每个场景约束(如低带宽、
  离线运行、实时性),方案里必须有真正处理它的机制与之对应;若各机制都不处理某约束
  (如全部机制都在单机上工作,没有任何数据走网络,则"低带宽"与方案无关),就不要在
  方案中反复渲染该约束——如实收窄场景;确需保留则写明需引入哪类架构(如分布式训练
  需"联邦学习架构+更新压缩+隐私机制"三层各司其职)并在字段 pending_decision 里注明
  "架构扩展待人工确认"。

硬规则:数据与现状描述只能来自 cited 单元;别人研究里的数字只作背景不作本项目基线;
严禁 U 编号写进任何字段值(引用单元用 from_units 字段);只输出 JSON,不要任何额外文字。
"""


def _check_experiments(plan, longevity=None):
    """确定性核查试验块:全干预因子块 2^k 完整性 / 交互有归宿 / 寿命块缺失 / 待人工块。"""
    warns = []
    exps = plan.get("experiments") or []
    for e in exps:
        fs = e.get("factors") or []
        if fs and all(f.get("kind") == "干预" for f in fs):
            k = len(fs)
            n_cfg = len(e.get("configs") or [])
            if 0 < k <= 3 and n_cfg < 2 ** k:
                warns.append(f"块「{e.get('name', e.get('id', '?'))}」为全干预因子块,"
                             f"配置仅 {n_cfg} 组、少于完整因子设计的 2^{k}={2 ** k} 组,"
                             f"缺组算不出对应交互效应")
    for it in plan.get("interactions") or []:
        pair = it.get("between") or []
        if pair and not any(all(str(p) in json.dumps(e, ensure_ascii=False) for p in pair)
                            for e in exps):
            warns.append(f"相互作用 {pair} 没有任何试验块能估计它(交互无归宿),"
                         f"请补进某块或删除该声称")
    if (longevity or {}).get("required") and exps and not any(
            "寿命" in str(e.get("type", "")) for e in exps):
        warns.append("目标含长期性/可靠性要求,但试验块清单里没有寿命循环块")
    for e in exps:
        if str(e.get("type", "")) == "待人工":
            warns.append(f"试验块「{e.get('name', '?')}」标记待人工:{e.get('reason', '')}")
    return warns


def step_decompose_uni(goal_text, cited, others, req, pins, dims, domain, skeleton, longevity):
    print("\n===== 二 统一框架分解(构建→集成→相互作用→实验设计) =====")
    user = DECOMP_UNI_USER.format(
        goal_text=goal_text,
        core_task=pins.get("core_task", ""), base_model=pins.get("base_model", ""),
        main_data=pins.get("main_data", ""),
        dims="、".join(d.get("name", "?") for d in dims),
        skeleton=skeleton or "- 块1 因子对照试验:按干预维度自组",
        cited=json.dumps(cited, ensure_ascii=False, indent=2),
        others=json.dumps(others, ensure_ascii=False, indent=2) if others else "(无)",
        req=req, domain=domain)
    plan = gg.parse_json(_llm(DECOMP_UNI_SYS, user, TEMP))
    layers = plan.get("layers") or []
    inters = plan.get("interactions") or []
    exps = plan.get("experiments") or []
    miss = [f for f in ("build", "layers", "interactions", "experiments") if not plan.get(f)]
    print(f"  构建基准: {'✓' if plan.get('build') else '✗ 缺失'} · 机制 {len(layers)} 层(干预) · "
          f"相互作用 {len(inters)} 组 · 试验块 {len(exps)} 块"
          + (f"  ⚠ 缺{miss}" if miss else ""))
    for l in layers:
        wk = all(o.get("weakness") for o in l.get("tech_options", []))
        print(f"    层·{l.get('dimension')}: {l.get('mechanism')}"
              f"{'' if wk else '  ⚠ 备选缺代价'}")
    for e in exps:
        print(f"    块·{e.get('type', '?')}: {e.get('name', '?')}")
    for w in _check_experiments(plan, longevity):
        print(f"  [警告] {w}(已交反思复查,并进人工复核清单)")
    gg.dump("design_items", plan)
    return plan


# ================================================================== 步骤二:扩写成四节
WRITE_SYS = (
    "你是国家级项目申报书的撰写专家,擅长把结构化研究方案写成连贯、具体、有说服力的正文。"
    "忠于给定材料,绝不编造数字,拟定指标须体现'拟定/预期'性质,绝不出现 U1 这类内部编号。"
)

WRITE_USER = """选定的研究目标(正文):
{goal_text}

已坐实的子研究内容(JSON):
{items}

方法单元对照表(id → 名称;正文提到某方法用名称,严禁出现 U 编号):
{umap}

团队/设备/数据等条件材料(可能为空):
{team}

研究需求/方向:{req}

本课题的【领域画像】(措辞与验证手段的依据,全文遵循):
{domain}

请写申报书的【研究方案】,分四节,每节一段或数段连贯散文,不要列表、不要小标题以外的编号:

(一)研究内容
把上面的子研究内容写成"研究内容分解":逐条说明本项目具体研究什么,每条都要落到
研究对象/数据、要解决的具体问题上,让人看得出是可执行的研究点,不空泛。

(二)思路方法
沿"对象/数据 → 技术手段 → 可验证产出"的逻辑,说明每个研究内容怎么做、按什么步骤推进、
产出如何衡量(拟定指标写成"拟/预期",不编造真实数值)。本节是"实验操作说明书":
只写怎么做、怎么分组、怎么测、怎么分析;涉及多因素实验时用全因子分析的语言
(主效应/交互效应,重复实验以均值与置信区间报告);拟定目标值仅在节末一句带过。

(三)比较优势
对每个研究内容,把备选技术路线摆出来对照(各自优缺点取自材料),说明本项目选定哪条、
为什么它相对其他路线有优势;提到现有方法用其名称。
【节间分工】本节是"技术选型说明书",只回答"凭什么选它不选别的",每个维度三件事:
有哪些候选、各自优缺点、为何选定其一。四条禁令:
- 不得出现具体数值目标或性能承诺(数值目标只属于(二),需要提及时定性写
  "具体目标见思路方法一节");优势只写由机制原理直接成立的**内在特性**,
  不写"能降低多少/效果更好"这类须实验才能证实的效果承诺;
- 不得论证可行性(那是(四)的事)——"方法成熟""工具完善""已广泛应用""有理论基础"
  这类论述一律归(四),本节不得出现;
- 不得以任何总结/升华句收尾——复述机制解决什么问题、宣称"共同支撑××创新/协同
  路径"都在禁止之列,最后一个维度的选定理由说完即收尾;
- 不得把方案中没有任何机制去处理的场景约束当作选型理由。

(四)可行性
分三层:理论可行(研究现状已有相关基础)、技术可行(依托的现有方法与基线、方法成熟度)、
条件可行(团队/设备/数据——有条件材料就据实写,没有就写"相关条件待补充",不要编造团队信息)。
【节间分工】本节只回答"凭什么做得成":不得重复(三)已做过的技术比较——不再摆备选
对照、不再论证选定理由;提及机制只谈其成熟度与实现依托。方法的理论基础、工具生态、
"已广泛应用"类论述都归本节的理论/技术层,不许留在(三)。

硬性要求:
1. 研究对象、数据集、现状基线数值只能来自子研究内容里已坐实的 object_data 和被引用
   单元;被引用单元没提供的写"待调研确定",绝不编造具体数据集名或基线数字。
   本项目目标值标"拟定/预期/待论证"。
2. 严禁 U1、U2 这类内部编号,也严禁"材料一""第X节"这类内部标签当出处;凡本提示里
   各材料的标题名称(读者看不到的内部指涉)一律不得写进正文。
3. 严禁未定义的数学指标(如"谱半径ρ>1"),改用平实的机制描述。
4. 避免"彻底解决""完全消除""首个""首次""率先""最优"这类绝对化措辞。
5. 每节直接从正文写起,四节各以"(一)研究内容""(二)思路方法"
   "(三)比较优势""(四)可行性"开头,不要额外前言,不要 markdown 标题符号(#);
   开头第一句直接进入实质内容,不要复读节标题(如"可行性论证从三个层面展开"这类)。
6. 措辞遵循文首【领域画像】:avoid 所列外行词不得出现,实验/验证手段须属于该领域惯例
   (可行性的替代验证方案按画像的 simulation 与 verification_methods 写)。
"""


def step_write(goal_text, items, cited, team, req, domain):
    print("\n===== 三 扩写研究方案四节 =====")
    # 对照表只给"被引用单元":扩写基线时看不到其他单元名字,减少越界与 U 编号泄漏
    umap = "\n".join(f"{u.get('id')} = {u.get('work')}" for u in cited)
    user = WRITE_USER.format(
        goal_text=goal_text,
        items=json.dumps(items, ensure_ascii=False, indent=2),
        umap=umap, team=team or "(无,条件可行留空标待补充)", req=req, domain=domain)
    prose = _clean(_llm(WRITE_SYS, user, TEMP))
    print(f"  完成 ({len(prose)} 字)")
    return prose


WRITE_UNI_USER = """选定的研究目标(正文):
{goal_text}

统一框架结构化底稿(JSON,含 build/layers/interactions/ablation):
{items}

方法单元对照表(id → 名称;正文提到某方法用名称,严禁出现 U 编号):
{umap}

团队/设备/数据等条件材料(可能为空):
{team}

研究需求/方向:{req}

本课题的【领域画像】(措辞与验证手段的依据,全文遵循):
{domain}

请写申报书的【研究方案】,分四节,每节一段或数段连贯散文,不要列表、不要小标题以外的编号。
全文主线:**所有机制作用于同一个基准模型、同一套主数据**,这句统一性必须在正文里明确写出,
不得写成几个各用各的数据与模型的并列实验。

(一)研究内容
按三块递进写:内容1"构建":围绕核心任务,在主数据上构建基准模型并测量基线;
内容2"逐层集成":在同一基准模型上依次集成各层机制(写明集成顺序与每层解决什么);
内容3"相互作用与权衡分析":研究各机制之间的相互影响(用底稿 interactions 的假设),
说明这是本项目的核心创新点。

(二)思路方法
写成一条流水线:构建基准并测量基线 → 依次开展底稿 experiments 里的各试验块。
逐块写清:试验名称与类型、因子与水平(寿命块则写对象/拟定循环规模/追踪量)、
回答哪些效应、统一指标集;因子表类的块用**全因子分析**的语言写分析方法——估计各因子
的主效应、两两交互效应与联合效应,并写明"各配置采用相同的数据划分与统一指标做重复
实验,以均值、标准差和置信区间报告结果",不要写成"组间做减法"式的表述;
块序按"先筛选、后确认"推进。本节是"实验操作说明书":只写怎么做、怎么分组、怎么测、
怎么分析;拟定目标值仅在节末用一句相对表述带过(注明具体数值由实验产生),不展开。

(三)比较优势
对每一层机制,把备选路线摆出来对照(优点与代价都写,取自底稿),说明选定理由;
提到现有方法用其名称。
【节间分工】本节是"技术选型说明书",只回答"凭什么选它不选别的",每个维度三件事:
有哪些候选、各自优缺点、为何选定其一。四条禁令:
- 不得出现具体数值目标或性能承诺(数值目标只属于(二),需要提及时定性写
  "具体目标见思路方法一节");优势只写由机制原理直接成立的**内在特性**,
  不写"能降低多少/效果更好"这类须实验才能证实的效果承诺;
- 不得论证可行性(那是(四)的事)——"方法成熟""工具完善""已广泛应用""有理论基础"
  这类论述一律归(四),本节不得出现;
- 不得以任何总结/升华句收尾——复述机制解决什么问题、宣称"共同支撑××创新/协同
  路径"都在禁止之列,最后一个维度的选定理由说完即收尾;
- 不得把方案中没有任何机制去处理的场景约束当作选型理由。

(四)可行性
分三层:理论可行(研究现状对各机制已有基础)、技术可行(基准模型与各机制的成熟度、
一个模型一套数据的集中验证路径)、条件可行(有条件材料就据实写,没有就写清拟采用的
替代验证方案——**方案必须贴合研究对象的领域**:按文首【领域画像】的 simulation
与 verification_methods 写,严禁照搬其他领域的验证手段,
其余真实团队/设备信息标"待补充",不要编造)。
【节间分工】本节只回答"凭什么做得成":不得重复(三)已做过的技术比较——不再摆备选
对照、不再论证选定理由;提及机制只谈其成熟度与实现依托。方法的理论基础、工具生态、
"已广泛应用"类论述都归本节的理论/技术层,不许留在(三)。
若方案的某维度依赖主数据具备特定字段/属性(如公平性分析需敏感群体属性),在本节
写入数据前提兜底句:"正式实验前将对数据的真实性、所需属性完整性与群体样本分布做
质量审查;若主数据无法支持,将选用具备所需属性的公开数据作为补充验证集"。

硬性要求:
1. 研究对象、数据集、现状基线数值只能来自底稿与被引用单元;没提供的写"待调研确定",
   绝不编造;本项目基线一律写"在主数据上先测量建立",目标值标"拟定/预期/待论证"。
2. 严禁 U1、U2 这类内部编号,也严禁"材料一""第X节"这类内部标签当出处;凡本提示里
   各材料的标题名称(读者看不到的内部指涉)一律不得写进正文。
3. 严禁未定义的数学指标(如"谱半径ρ>1"),改用平实的机制描述。
4. 避免"彻底解决""完全消除""首个""首次""率先""最优"这类绝对化措辞。
5. 每节直接从正文写起,四节各以"(一)研究内容""(二)思路方法"
   "(三)比较优势""(四)可行性"开头,不要额外前言,不要 markdown 标题符号(#);
   开头第一句直接进入实质内容,不要复读节标题(如"可行性论证从三个层面展开"这类)。
6. 技术机理与环境表述要准确自洽,典型反例(同类错误一律避免):
   - INT8 量化的机理是"降低参数与激活值数值精度,减少存储与内存访问开销,并在支持
     低精度指令的硬件上提升推理效率",不是"减少运算次数";
   - 论证某硬件环境的可行性,引用的工具必须属于该环境(CPU 推理引 PyTorch 静态量化/
     ONNX Runtime/TensorFlow Lite/OpenVINO,不要引 GPU 侧的 TensorRT);
   - (仅计算/AI 类课题适用)模拟"低资源终端"用"无独立 GPU 的普通设备+容器限核限内存限带宽",不要写"集群"
     (集群意味着资源丰富,与低资源矛盾;仅当模拟多客户端服务端时才可用一台服务器,
     且须写明每客户端的资源上限);
   - 速度类目标必须绑定效用下限成对出现(如"延迟降低拟定X%,同时 AUC 或宏平均 F1
     下降不超过拟定阈值"),防止拿性能换速度而不自知。
7. 同一指标全文只能有一种口径:不得一处写死数值、另一处又写"待实验确定";统一为
   "拟定值(待实验论证)"或统一为相对表述。
"""


def step_write_uni(goal_text, plan, cited, team, req, domain):
    print("\n===== 三 扩写研究方案四节(统一框架) =====")
    umap = "\n".join(f"{u.get('id')} = {u.get('work')}" for u in cited)
    user = WRITE_UNI_USER.format(
        goal_text=goal_text,
        items=json.dumps(plan, ensure_ascii=False, indent=2),
        umap=umap, team=team or "(无,条件可行按'拟采用模拟方案+真实信息待补充'写)", req=req,
        domain=domain)
    prose = _clean(_llm(WRITE_SYS, user, TEMP))
    print(f"  完成 ({len(prose)} 字)")
    return prose


# ================================================================== 步骤三:反思(精简单镜头)
REVIEW_SYS = (
    "你是省部级项目申报书的严格评审专家。逐条对照标准检查研究方案文稿,只报实质问题,"
    "不吹毛求疵。"
)

REVIEW_USER = """待审研究方案:
{prose}

已坐实的子研究内容(核对用):
{items}

被本目标引用的方法单元(溯源核对用,研究对象/基线应来自这里):
{cited}

本课题的【领域画像】(词汇渗漏与验证手段检查的依据):
{domain}

请按以下标准检查,只报实质问题:
1. 坐实充分:每个研究内容是否说清了"研究对象/数据、技术手段、可验证产出"?
   有没有停留在"研究轻量化方法""提升公平性"这类没有可验证产出的空话?
2. 技术比较有据:技术途径的比较优势是否基于真实方法的优缺点,而不是空口自夸?
   有没有该比较却只讲选定路线、没摆出对照的?**节间分工**:比较优势节里有没有越界
   写数值目标/性能承诺(应属思路与方法节)或可行性论证(应属可行性节)——"方法成熟/
   工具完善/已广泛应用/有理论基础"混进(三)即越界?优势有没有写成待实验验证的效果
   承诺(应为机制原理直接成立的内在特性)?有没有以总结/升华句收尾(复述机制解决什么、
   宣称"共同支撑××创新"均算)?可行性节里有没有重复技术比较(重摆备选对照、
   重复选定理由)?同一数值目标在两节出现两种口径(一处写死、一处待定)也是缺陷。
3. 防幻觉:数字是否都来自材料或标注了"拟定/预期/待论证"?有无编造的真实基线或团队条件?
4. 溯源真实性:研究对象/数据集、现状基线数值是否取自"被引用单元"的 data_scene/metrics?
   有没有凭空编造数据集名、或挪用未被本目标引用的单元的数据?被引用单元没提供的,
   是否老实写了"待调研确定"?
5. 手段—目标对应:(a) 每个技术手段是否真能解决它声称的问题?尤其**隐私维度**:有没有
   把联邦学习、通信协议优化当成隐私保护(它们是分布式架构与提效手段,不是隐私机制;
   真隐私需差分隐私/安全聚合/加密)?若用联邦学习,是否写明另配了真正的隐私机制?
   (b) **场景约束悬空**:需求里渲染的场景约束(如低带宽、离线、实时),方案里有没有真正
   处理它的机制?若所有机制都与该约束无关(如全在单机工作却大谈低带宽),是缺陷——
   应收窄场景或补对应架构。
6. 基线与指标:(a) 有没有把别人特定研究/群体的数字直接当成
   本项目实验基线,而不是"在本项目数据上先测量建立基线"?(b) 有没有拍脑袋的绝对阈值
   不注明测量条件?应优先相对量。(c) 隐私维度是否只测了延迟、
   缺隐私强度指标(应写(ε,δ)-差分隐私并注明样本级/用户级粒度、可加成员推断AUC)?
   (d) **基线可测性**:基线指标列表里有没有"机制未引入就不存在"的指标(如基准模型
   没加隐私机制却列'隐私保护延迟')?这类应改为"机制引入后相对基线的额外开销"。
   (e) **口径一致**:同一指标是否一处定死数值、另一处又写"待定"?(f) **术语规范**:
   指标是否用标准术语,自造名称(如"偏见比例")是否给了定义?公平类是否多指标报告?
   (g) 速度类目标是否绑定了效用下限(不绑=可能拿性能换速度)?
   (h) **比例分母与阈值口径**:比例/倍数指标(如"能耗比例≤1%")写没写分母?
   阈值指标(如"12.5mm除冰厚度")有没有操作性定义(是初始条件、去除量还是残余量)?
   与他法对比时双方分母是否一致?
   (i) **尺度外推**:目标声称的应用范围是否超出主数据支持范围(如3米数据写"确保
   10米达成")而没有"校准→中间尺度→目标范围"的分级验证路径?
7. 技术对象具体:技术手段作用的模型是否具体且兼容?有没有"对机器学习方法做INT8量化"
   这种(量化只适用神经网络,不适用随机森林/GBM)的对象过宽或不匹配?
8. 比较双面:技术比较里选定路线是否也如实写了自身代价,而非只有优点、一边倒自夸?
   优点有没有写成无代价的绝对断言(如"不增加额外能耗""不影响精度")?应为条件化表述。
9. 可行性得当:可行性是否分理论/技术/条件三层?条件可行在无材料时是否老实写"待补充"、
   而非编造团队设备?有无"彻底解决/完全消除/首个/首次/率先/最优"等绝对化措辞?
   工具与环境是否匹配(CPU 可行性不得引 GPU 侧工具如 TensorRT;"低资源终端"不得用
   "集群"模拟)?依赖数据特定属性的维度,是否写了数据前提审查与补充验证集的兜底?
10. 表述规范:有无 U 编号、内部标签(材料一/第X节,以及本提示里各材料的标题名称——
   这些读者都看不到)、未定义数学指标(谱半径)、前言引导句、markdown 标题符号(#)?
   有无跨领域词汇渗漏——对照上方【领域画像】,正文出现 vocabulary.avoid 所列外行词、
   或验证手段不属于该领域惯例的,均为缺陷;**avoid 为空不代表免检**,仍须按"这个词
   在该领域的论文里是否自然出现"的统一标准,逐段自查是否混入其他领域的词汇。
{uni_std}
严格输出一个 JSON 对象:
- issues:数组,每项含 section(一/二/三/四)、std(标准编号)、quote(问题原文短片段)、
  problem(一句话)、fix(具体修改指令);无实质问题则空数组
- verdict:"通过" 或 "需修订"
只输出 JSON,不要额外文字。
"""

UNI_STD = """11. 统一性与实验设计(本方案声称统一框架,必查):所有干预机制是否明确作用于
   **同一基准载体、同一套主数据**?正文有没有写出这句统一性?研究内容是否含
   "相互作用/权衡分析"且给出了度量方式?实验设计是否按试验块写清,且**能分离
   主效应与交互效应**——全二元干预的因子块,配置是否列全 2^k 组(数一数!缺任何
   一组就算不出对应交互,是缺陷;资源有限只许标"补充",不许缺组)?声称的每组
   相互作用是否有某个试验块能估计它(两因子同表)?条件因子有没有被错写成可开/关
   的"机制"、或出现"仅启用某条件"这类物理上不存在的配置?目标若含长期性/可靠性
   要求,是否有寿命循环块?有没有退化成几个各用各的数据与载体的并列实验?
"""

REVISE_SYS = (
    "你是国家级项目申报书撰写专家。按评审意见精修研究方案:只修被点名处,不新增事实和数字,"
    "不改动未被点名的内容,保持四节结构与篇幅量级。"
)


def step_review(prose, items, cited, mode="linear", domain="(无)"):
    print("\n===== 四 反思:研究方案质量审查 =====")
    user = REVIEW_USER.format(prose=prose, items=json.dumps(items, ensure_ascii=False, indent=2),
                              cited=json.dumps(cited, ensure_ascii=False, indent=2),
                              domain=domain,
                              uni_std=UNI_STD if mode == "unified" else "")
    r = gg.parse_json(_llm(REVIEW_SYS, user, gg.TEMP_A))
    issues = r.get("issues", []) or []
    verdict = r.get("verdict", "需修订" if issues else "通过")
    for i, it in enumerate(issues, 1):
        print(f"  问题{i} [第{it.get('section')}节|标准{it.get('std')}] {it.get('problem')}")
        print(f"        原文: {it.get('quote')}")
        print(f"        修改: {it.get('fix')}")
    print(f"  评审结论: {verdict}({len(issues)} 条)")
    gg.dump("design_review", r)
    return issues


def step_revise(prose, issues):
    print("\n===== 五 修订 =====")
    user = ("原稿:\n" + prose + "\n\n评审意见(JSON,逐条修复):\n"
            + json.dumps(issues, ensure_ascii=False, indent=2)
            + "\n\n修订要求:"
            "\n- 越界基线/数据来源不真实:删掉越界的具体基线数字,改为'以现有相关方法为参照';"
            "\n- 别人的数字当基线:改为'在所选数据上先测量建立本项目基线,相对基线改善拟定X%';"
            "\n- 联邦学习/通信压缩当隐私:补上'另结合差分隐私/安全聚合提供隐私保障',或改回它真实的作用(架构/提效);"
            "\n- 绝对阈值无条件:改成相对量,或补测量条件;隐私维度补隐私强度指标(ε等);"
            "\n- 技术对象过宽:改成具体且兼容的模型(如轻量级神经网络);"
            "\n- 比较一边倒:给选定路线补上自身代价;"
            "\n- 退化成并列实验(统一框架方案):明确写出所有机制作用于同一基准模型、"
            "同一主数据,补齐相互作用分析与消融配置的表述;"
            "\n- 残留 U 编号一律换成方法名称。"
            "\n只输出研究方案正文四节本身,直接从'(一)研究内容'开头,严禁任何标题、开场白,"
            "严禁 markdown 井号(#),严禁末尾附'修订说明/修改说明'这类元信息段落。")
    out = _clean(_llm(REVISE_SYS, user, TEMP))
    print(f"  修订完成 ({len(out)} 字)")
    return out


# ================================================================== 数字 tripwire
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def check_numbers(prose, source_text):
    src = set(_NUM.findall(source_text))
    sus = [n for n in dict.fromkeys(_NUM.findall(prose)) if n not in src]
    # 邻近有"拟/预期/待/约"等限定词的拟定值不算可疑
    ok = []
    for n in sus:
        m = re.search(r".{0,6}" + re.escape(n) + r".{0,6}", prose)
        ctx = m.group(0) if m else ""
        if not re.search(r"拟|预期|待论证|待确定|约|左右|以内|不超过", ctx):
            ok.append(n)
    return ok


def check_borrowed_baseline(prose, cited):
    """确定性 tripwire:被引单元 metrics 里的文献数字,若出现在"基线/降至/提升至"
    这类措辞附近,多半是把别人的数字当成了本项目基线——警示交人工核。"""
    nums = set()
    for u in cited:
        for m in (u.get("metrics") or []):
            nums.update(_NUM.findall(str(m.get("value", ""))))
    hits = []
    for n in nums:
        for mm in re.finditer(re.escape(n), prose):
            ctx = prose[max(0, mm.start() - 14):mm.end() + 14]
            if re.search(r"基线|基准值|降至|提升至|从.{0,6}倍|现有水平", ctx):
                hits.append(f"「{n}」…{ctx.strip()}…")
                break
    return hits


def _leaks(prose):
    leaks = sorted(set(re.findall(r"U\d+", prose)))
    leaks += sorted(set(re.findall(r"材料[一二12][^,。;)()]{0,6}", prose)))
    leaks += sorted(set(re.findall(r"谱半径|spectral radius", prose)))
    leaks += sorted(set(re.findall(r"领域画像", prose)))     # 内部材料标题禁入正文
    return leaks


STRIP_SYS = (
    "你是文字编辑。把正文里残留的内部单元编号(U1、U2 等)替换成对应的方法名称,"
    "对照表里查不到的编号用'现有相关方法'概括;不改动其他任何内容,不增删事实和数字。"
)


def step_strip_uid(prose, units):
    """出稿兜底:正文残留 U 编号时,专项把编号换成方法名称(不动其他内容)。"""
    umap = "\n".join(f"{u.get('id')} = {u.get('work')}" for u in units)
    user = ("方法单元对照表:\n" + umap
            + "\n\n下面的正文里残留了 U 编号,请把每个 U 编号替换成对照表里对应的方法名称"
              "(查不到的用'现有相关方法'),其余一字不改,只输出替换后的正文:\n\n" + prose)
    return _clean(_llm(STRIP_SYS, user, gg.TEMP_A))


# ================================================================== 主流程
def gen_design(team, req):
    idx, goal_text, cand, cited_ids = load_selected()
    units = load_units()
    print(f"\n选定目标: 第 {idx} 个")
    print(f"研究需求: {req}")

    # 精准溯源:研究对象/基线只认选定目标引用的单元;其余单元仅作技术比较备选池
    cited = [u for u in units if u.get("id") in cited_ids]
    others = [u for u in units if u.get("id") not in cited_ids]
    if cited:
        print(f"  精准溯源:选定目标引用 {[u.get('id') for u in cited]},"
              f"研究对象/基线只认这些单元(其余 {len(others)} 个仅供技术比较备选)")
    else:
        cited, others = units, []
        print("  未拿到引用指针(降级):研究对象/基线放宽到全部 units,仍禁编造具体数据集")

    # 步骤零:领域画像——先认领域,产出措辞/验证惯例,钉子/分解/扩写/评审全程遵循
    profile = step_domain(goal_text, cited, req)
    domain = _domain_block(profile)

    # 钉子与维度分类:模型提议→代码按真值表推模式/骨架→人工确认(非交互自动采纳)
    mode, pins, dims, longevity, skeleton, plan_warns, pins_auto = step_pins(
        goal_text, cited, req, domain)

    if mode == "unified":
        items = step_decompose_uni(goal_text, cited, others, req, pins, dims, domain,
                                   skeleton, longevity)
        prose = step_write_uni(goal_text, items, cited, team, req, domain)
    else:
        items = step_decompose(goal_text, cand, cited, others, req, domain)
        prose = step_write(goal_text, items, cited, team, req, domain)

    src_text = json.dumps(items, ensure_ascii=False) + "\n" + goal_text + "\n" + \
        json.dumps(units, ensure_ascii=False) + "\n" + json.dumps(pins, ensure_ascii=False) + \
        "\n" + json.dumps(dims, ensure_ascii=False)

    # 反思→修订循环:通过或满 2 轮才出稿(rubric 10~11 条,一轮常不够)
    passed = False
    for rnd in range(1, 3):
        issues = step_review(prose, items, cited, mode, domain)
        if not issues:
            print(f"  第 {rnd} 轮评审通过")
            passed = True
            break
        prose = step_revise(prose, issues)

    print("\n===== 出稿前核对 =====")
    leaks = _leaks(prose)
    u_leaks = [x for x in leaks if re.fullmatch(r"U\d+", x)]   # 残留 U 编号 → 专项剥离兜底
    if u_leaks:
        print(f"  [兜底] 检测到残留 U 编号 {u_leaks},追加一轮剥离")
        prose = step_strip_uid(prose, units)
        leaks = _leaks(prose)
    if leaks:
        print(f"  [警告] 残留内部指涉/未定义指标 {leaks}")
    sus = check_numbers(prose, src_text)
    if sus:
        print(f"  [数字警示] 未标注拟定/来源不明的数字: {sus}")
    else:
        print("  [数字核对] 数字均可溯源或已标注拟定")
    borrowed = check_borrowed_baseline(prose, cited)
    if borrowed:
        print(f"  [基线警示] 文献数字疑被当作本项目基线: {borrowed}")

    # 人工复核清单
    notes = []
    if isinstance(items, dict):                       # 统一框架:试验块确定性核查
        for w in _check_experiments(items, longevity):
            notes.append(f"- [实验设计] {w};请核对成稿是否已在修订中处理,未处理则手工修。")
    for w in plan_warns:
        notes.append(f"- [实验设计] {w}。")
    if leaks:
        notes.append(f"- [内部指涉] 正文残留 {leaks},改为方法名称/平实描述或删除。")
    for n in sus:
        notes.append(f"- [数字] 「{n}」未标注拟定且来源不明,请核实或标注'拟定/预期'。")
    for b in borrowed:
        notes.append(f"- [基线] {b} ——文献数字疑被当作本项目基线,应改为"
                     f"'在主数据上先测量建立本项目基线,相对基线改善拟定X%',文献值仅作背景。")
    if profile.get("auto_accepted"):
        notes.append("- [领域画像] 非交互环境自动采纳了领域判断(见 output/design_domain.json),"
                     "请确认 field/vocabulary/simulation 贴合课题领域;不符请在交互终端重跑,"
                     "或直接修改该 json 后重跑本脚本。")
    if pins_auto:
        notes.append(f"- [结构模式] 非交互环境自动采纳了建议({'统一框架' if mode == 'unified' else '线性'})"
                     f"与钉子提议(见 output/design_pins.json),请确认核心任务/基准模型/主数据"
                     f"符合你的科研意图;不符请在交互终端重跑本脚本改选。")
    if not team:
        notes.append("- [条件可行] 未提供团队/设备/数据材料,'条件可行'一节留空标待补充;"
                     "有条件请传 txt 重跑(python design\\design_gen.py 你的条件.txt)。")
    if not passed:
        notes.append("- [评审遗留] 评审点名的问题已自动修订、未再复审,建议对照 "
                     "output/design_review.json 抽查。")
    block = ("\n\n" + "=" * 30 + "\n【人工复核清单】(逐条处理后删除本区块再交稿)\n"
             + "\n".join(notes) + "\n") if notes else \
            ("\n\n" + "=" * 30 + "\n【人工复核清单】无待复核项。交稿前删除本行。\n")

    final = prose + block
    out = OUT_DIR / "design.txt"
    out.write_text(final, encoding="utf-8")
    print(f"\n  [已存盘] {out}")
    print("\n===== 研究方案成稿 =====\n")
    print(final)
    return final


if __name__ == "__main__":
    team = ""
    if len(sys.argv) > 1:
        tp = Path(sys.argv[1])
        if tp.exists():
            team = tp.read_text(encoding="utf-8").strip()
            print(f"团队/设备/数据材料: {tp} ({len(team)} 字)")
        else:
            print(f"[提示] 找不到 {tp},条件可行将留空")

    meta = OUT_DIR / "overview_meta.json"
    req = json.loads(meta.read_text(encoding="utf-8")).get("requirement", "") if meta.exists() else ""
    print(f"模型: {gg.MODEL}")
    gen_design(team, req)
