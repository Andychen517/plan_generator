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
import goal_gen as gg          # 复用 call_llm / parse_json / A 步 prompt / OUT_DIR

# 全链固定中文出稿(英文版由 translate_en.py 翻译成稿),直接沿用 goal_gen 的语言指令

OUT_DIR = gg.OUT_DIR
TEMP_PROSE = 0.4
MAX_REFLECT_ROUNDS = 2         # 反思->修订 最多两轮,仍不过就标"需人工复核"


def _llm(system: str, user: str, temperature: float) -> str:
    """LLM 调用统一入口:重试提到 8 次(退避 3s~21s),扛代理瞬时断连。"""
    return gg.call_llm(system, user, temperature, max_retries=8)


# ================================================================== 生成 prompt
XUQIU_SYS = (
    "你是国家级项目申报书的撰写专家,擅长写『需求分析』一节。"
    "只依据给定材料,绝不编造;引用的数字必须原样来自材料。"
    "文风克制、严谨:数据宁少勿滥,表述避免绝对化。"
)

XUQIU_USER = """材料一:一份研究现状综述的原文(可能是英文,其引言部分讲了研究背景)。
材料二:从该综述结构化抽取的方法单元(JSON,solves 是各方法要解决的问题,
limitation 是现实痛点/短板)。另附本项目的研究需求/方向。

研究需求/方向:{req}

材料一(综述原文):
{review}

材料二(方法单元):
{units}

请据此写申报书的【需求分析】,按四个自然段展开:
第一段:该领域的现实需求——使用群体(如学生、教师、学校、管理部门)面临什么真实
       需求和负担(如个体差异、师资负担、资源不均),依据取自材料,不空喊口号;
第二段:归纳现有系统为什么满足不了这些需求——把痛点收成 3~4 类障碍主线
       (如 成本与可扩展性 / 公平性 / 可靠性 / 隐私与合规),概括性描述为主,
       不要逐一点名罗列具体模型和技术路线(那是研究现状的事);
第三段:明确本项目面向的主要场景(如低资源学校、在线教育平台等,从材料和需求方向推);
第四段:围绕一条明确主线,提出 2~3 个核心研究问题(不要试图覆盖所有治理问题),
       与研究需求方向一致,问题之间层层递进。

硬性要求:
1. 数字克制:全文至多保留 3~5 个最能支撑"必要性"的核心数字,每个都要
   (a) 加限定语,如"部分研究显示""在某项针对……的研究中",不写成普适断言;
   (b) 尽量注明来源(材料里有作者/机构/年份就带上);
   其余痛点一律定性概括。数字必须原样来自材料,不得编造或改动。
   注明来源时只能写真实的作者/机构/年份;严禁把"材料一""材料二""第X节"这类
   内部标签当出处写进正文(读者看不到这些材料),材料里没有真实出处就不注。
2. 证据选择:数字必须与它支撑的论点因果直接相关(如师资短缺、设备覆盖率、
   城乡成绩差距之于个性化学习需求);因果间接的宏观统计(如入学率)不作核心证据。
   数字的语义不得改写(能力水平15% 不等于 15%的人达标;降幅不等于基线)。
3. 主线与研究问题对齐(重要):
   (a) 主线里声称的每个维度,都必须有一个研究问题实际覆盖;覆盖不了就把主线收窄,
       宁窄勿宽——第二段大篇幅强调、但研究问题不打算解决的障碍,要明确降为背景;
   (b) 每个研究问题的所有要素必须与第三段限定的场景直接匹配,不得为拔高引入
       场景外要素(如面向国内场景就不写跨境合规,合规按国内法规写);
   (c) 研究问题中不得出现任何拟定数值指标(如"R²≥0.96""达到95%"),性能约束用
       "在核心任务性能基本不下降的前提下"这类表述,具体指标留到研究方案按任务再定。
4. 表述严谨:避免"无效""冲突"这类绝对化措辞(改用"仍然有限""合规要求存在差异,
   增加部署复杂度"等);不引入材料外的数学指标或未定义的术语(如谱半径),
   偏差放大这类机制用平实语言描述(如"预测结果反过来影响后续数据,形成反馈回路")。
5. 术语规范:中文为主;术语首次出现写"中文(英文全称)",之后用中文简称或英文缩写,
   不要反复写完整英文名称。
6. 连贯散文,共四个自然段,合计 500~700 字;不要小标题、不要列表、不要编号,
   严禁出现 U1、U2 这类内部编号。
7. 直接从正文开头写起,严禁任何前言或引导句(如"以下是…""好的…")。
"""

XIANZHUANG_SYS = (
    "你是国家级项目申报书的撰写专家,擅长写『研究现状』一节。"
    "忠于给定综述原文,只做翻译、压缩和重组,绝不编造;引用的数字必须与原文一致。"
    "文风克制、严谨:数据宁少勿滥,表述避免绝对化。"
)

XIANZHUANG_USER = """下面是一份研究现状综述的原文(可能是英文),以及本项目的研究需求/方向。

研究需求/方向:{req}

综述原文:
{review}

请把它改写成申报书的【研究现状】(中文),要求:

一、组织方式(最重要):
1. 不要把不同层级的概念并列成平行的"技术路线"(应用系统、建模方法、支撑设施是
   不同层级,混排会交叉重复)。改为按"教育应用主题/问题域"分 4~5 个自然段组织,
   例如:学习者建模与风险预测 / 个性化资源推荐与路径规划 / 智能辅导与生成式反馈 /
   自动评估 / 公平性、隐私与可信 AI 支撑技术(具体按综述实际内容取舍归并)。
   与研究需求方向关系远的主题一笔带过或不写,不要让综述范围扩张。
2. 每个主题段内按固定结构展开:方法原理 → 代表性应用(国内外进展,原文点明了
   国别/机构的要体现;没说的不硬安)→ 已取得成效 → 主要局限,并在段尾用一句话
   回扣本项目的场景/需求方向(如"在……环境下其稳定性与可部署性仍有待验证"),
   让每一段都服务于最终研究空白。句子不要过长,一句话别同时塞方法、案例、指标、优缺点。
3. 若把公平性与隐私等合并为一段,段内用"在公平性方面……""在隐私保护方面……"分层,
   避免偏见、加密、延迟、法规差异挤在一处。

二、定量描述(克制而准确):
4. 每个主题段保留 1~2 个最有代表性的数字即可,其余定性概括;每个数字
   (a) 加限定语("部分研究显示""在某项……试验中"),(b) 尽量带来源(作者/机构/年份),
   (c) 数值、条件、语义都与原文一致,不得编造、改动或张冠李戴。
5. 异常好的指标(如 R²≈0.9997 这类接近完美的结果)不要当作代表性进展直接引用:
   要么略去,要么明确注明其评估条件有待核实。含义不明的缩写指标(如 SLI)
   不使用,或先用一句话解释清楚。指涉不明的数字(说不清主体、条件、来自哪项研究)
   宁可删去。
6. 实体归属要准确:写"某机构的研究基于 XX 数据集评估了 YY 模型",不得写成
   "YY 模型(某机构)"这类会造成归属错误的括注。

三、表述与用语:
7. 避免绝对化措辞("无效"→"仍然有限";"监管冲突"→"合规要求存在差异,增加跨区域
   部署复杂度")。不引入未定义的数学指标(如谱半径),机制用平实语言描述。
   别扭的直译名称(如"Beyond GANs")改为自然中文表述(如"生成式人工智能与合成数据技术")。
8. 术语规范:中文为主;术语首次出现写"中文(英文全称)",之后用中文简称或英文缩写。

四、收尾:
9. 最后用 2~3 句综合评述归纳研究空白:现有研究往往各自优化自己的指标,缺少针对
   本项目场景核心限制(点出具体限制,如低算力、低带宽、数据稀疏)的协同优化机制。
   措辞必须与研究需求方向的维度一一对应,避免"统一框架解决所有问题"式的过大表述。
10. 全文 600~900 字,若干自然段;不要小标题、不要列表、不要编号、不要粗体标记。
11. 直接从正文开头写起,严禁任何前言或引导句。
"""


# ================================================================== 反思三镜头
# 每条 rubric 都是主题无关的通用标准,来自 2026-07-17 两轮人工评审的教训固化。
LENS1_SYS = (
    "你是项目论证的逻辑评审专家,专查申报书内部的一致性:研究场景、技术主线、"
    "障碍归纳、核心研究问题、结论评述五者是否互相对齐。只依据文稿本身判断,"
    "不吹毛求疵,只报实质问题。"
)

LENS1_TAIL = """

请先把文稿骨架抽出来,再做四项对齐检查:
(a) 声称覆盖:主线和结论声称的每个维度,是否都有核心研究问题实际覆盖?
    没被覆盖的维度是缺陷。修改建议默认"收窄声称"(从主线/结论中删去该维度,
    并把需求分析里对它的大篇幅强调降为背景),除非文稿显示它确是核心研究内容。
(b) 障碍归宿:需求分析重点强调的每类障碍,要么有研究问题对应,要么只作背景
    一笔带过;大篇幅强调却无问题对应的,是缺陷。
(c) 场景匹配:每个研究问题的每个要素,是否与文稿限定的场景自然相关?
    与场景无关、疑似为拔高而加的要素(如面向国内单一场景却要求跨境/多国合规),
    是缺陷,请给出贴合场景的替代表述。
(d) 结论对齐:结尾研究空白/综合评述的措辞,是否与核心研究问题精确对应、具体?
    "统一框架""解决所有问题"式的过大表述是缺陷,请给出对齐研究问题的具体改法。

判定注意(以下情况不算缺陷,不要报):
- (b) 只有成句、成段的重点强调且完全无归宿才算;从句里一笔带过的提法不算。
  障碍与研究问题只需合理关联即算有归宿(如"开发成本高"之于轻量化问题、
  "数据稀疏"之于公平性约束问题),不必逐字对应。
- (d) 结论与研究问题的维度一致即可,概括性措辞(如"协同优化机制")不算过大;
  只有明显超出研究问题范围的("统一框架""所有问题")才算。
- 研究问题不必逐字复述场景要素,自然相关即可。

严格输出一个 JSON 对象,字段:
- skeleton:对象,含 scene(场景一句话)、mainline_dims(主线声称的维度列表)、
  key_obstacles(需求分析重点障碍列表)、research_questions(数组,每项含
  text_short 一句话概括 和 covers_dims 覆盖的维度列表)、conclusion_dims(结论声称的维度列表)
- issues:数组,每项含 section("需求分析"/"研究现状")、lens("一致性")、
  check("a"/"b"/"c"/"d")、quote(有问题的原文短片段)、problem(一句话)、fix(具体修改指令)
- verdict:"通过" 或 "需修订"
只输出 JSON,不要任何额外文字。
"""

LENS2_SYS = (
    "你是严格的事实核查员,核对申报书文稿与其来源材料。只依据给定材料判断,"
    "不吹毛求疵,只报实质问题。"
)

LENS2_TAIL = """

请对文稿做四项忠实性检查(对照上面的来源材料):
(a) 语义忠实:数字和结论的含义是否与材料一致?典型错误:把"能力水平15%"写成
    "15%的人达标"、把降幅当基线、把毛入学率写成升学率。数值对但语义变,也是缺陷。
(b) 归属准确:模型/系统/数据集/结果的机构、作者归属是否与材料一致?典型错误:
    "Qwen2.5-7B 模型(某大学)"——模型不属于该机构,应写"某机构的研究评估了该模型"。
(c) 指涉明确:文稿里每个数字,能否从材料说清它的主体和条件(谁、在什么研究/环境下)?
    指涉不明、读者无从判断含义的数字,建议删除,并在 fix 里写明。
(d) 证据相关:关键证据与它支撑的论点是否因果直接相关?用因果间接的宏观统计
    (如入学率之于个性化学习需求)当核心证据,是缺陷;建议换材料里更直接的证据或改定性表述。

判定注意(以下情况不算缺陷,不要报):
- (c) 只审文稿中"出现了的数字"。定性表述(如"延迟明显增加""成本偏高")不是缺陷,
  严禁建议给定性表述补数字——少用数字正是文稿的要求。
  带限定语("部分研究显示"等)且能在材料中找到对应表述的数字,不算指涉不明。
- 文稿是对材料的概括,允许合理的归纳措辞;只有语义实质改变、或材料完全无依据时才报。

严格输出一个 JSON 对象,字段:
- issues:数组,每项含 section("需求分析"/"研究现状")、lens("忠实性")、
  check("a"/"b"/"c"/"d")、quote、problem、fix
- verdict:"通过" 或 "需修订"
只输出 JSON,不要任何额外文字。
"""

LENS3_SYS = (
    "你是省部级项目申报书的文字评审专家,专查数据使用与表达规范。"
    "不吹毛求疵,只报实质问题。"
)

LENS3_TAIL = """

请对文稿做六项表达规范检查:
(a) 数据密度:需求分析全文核心数字≤5 个,研究现状每主题段≤2 个;超出即缺陷,
    fix 里指明保留哪些、删掉哪些(保留最能支撑论点的)。
(b) 限定与来源:每个数字是否带限定语("部分研究显示"等)并尽量注明来源?
(c) 拟定数值目标:研究问题中出现任何拟定的数值指标(如"R²≥0.96""达到95%")即缺陷,
    改为"在核心任务性能基本不下降的前提下"类表述。
(d) 严谨措辞:绝对化词(无效/彻底解决/完全消除/首个/最优/监管冲突)、未定义的数学
    指标或缩写、接近完美的异常指标(R²≥0.99、99%+)被当代表性进展,均为缺陷。
(e) 术语与语病:术语首现应"中文(英文全称)"、之后用简称;有无语病(如"硬件配置基础"
    应为"硬件基础薄弱")、过长的句子、前言/引导句、小标题/粗体、U1 类内部编号、
    "材料一/材料二/第X节"这类内部材料标签被当成出处(读者看不到,须删或换真实出处)。
(f) 两节重复:需求分析与研究现状是否大量重复同样的数字和案例?

判定注意(以下情况不算缺陷,不要报):
- (b) 材料本身没给更具体出处时,数字带限定语即可,不必强求作者/年份。
- (e) 大众熟知的缩写(如 GPU、AI、K-12、GDPR)不要求写英文全称;仅专业术语首现需要。
- 只报实质问题;可报可不报的一律不报。

严格输出一个 JSON 对象,字段:
- issues:数组,每项含 section("需求分析"/"研究现状")、lens("表达")、
  check("a"~"f")、quote、problem、fix
- verdict:"通过" 或 "需修订"
只输出 JSON,不要任何额外文字。
"""

REVISE_SYS = (
    "你是国家级项目申报书的撰写专家。按评审意见精修文稿:只修被点名的问题,"
    "不新增事实和数字,不改动未被点名的内容,保持原有结构和篇幅量级。"
    "对'声称未覆盖'类问题,除非 fix 明确要求补研究问题,一律选择收窄声称。"
)

REVISE_TAIL = """

输出修订后的全文,格式严格如下(方便程序切分,不要任何多余文字):
(一)需求分析
<修订后的需求分析正文>

(二)研究现状
<修订后的研究现状正文>
"""


# ================================================================== 代码 tripwire
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


# ================================================================== 工具
def _clean_prose(text: str) -> str:
    """剥 r1 思维块 / 代码围栏 / 开头引导句(与 goal_gen.step_d 同款兜底)。"""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"```(?:\w+)?", "", text).strip()
    text = re.sub(r"^\s*(based on|here is|below is|the following is|好的|以下是|下面是|以下为)[^\n]*?[:：]\s*",
                  "", text, flags=re.IGNORECASE).strip()
    # 再兜一层:开头"××综述如下。/概述如下:"式引导句(生成 prompt 已禁,防漏网变体)
    text = re.sub(r"^[^\n。:：]{0,40}如下[。::]\s*", "", text).strip()
    return text


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


# ================================================================== 主入口
if __name__ == "__main__":
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
