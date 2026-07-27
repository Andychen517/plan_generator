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
from prompts_design import *          # 提示词全部集中在 prompts_design.py

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
