# -*- coding: utf-8 -*-
"""全链可调参数,一站式集中——改参数只动这个文件。

模型与密钥不在这里:模型名走 .env.local 的 CUSTOM_MODEL,密钥同文件
(模板见 .env.example);客户端初始化在 llm_core.py。
"""

N_GOALS = 3          # 目标数上限(宁缺毋滥,真 gap 有几个就出几个)

# ——通用性开关:关掉后 goal_gen 不再强求综述里有这些信息,输出更通用——
WITH_ORIGIN = True   # A 是否抽"国内外";False=不抽,单元更干净
WITH_QUANT = True    # 是否做整套"定量增量"(A抽指标/C产增量/D写增量/反思查数值);False=全部跳过

# ——输出语言:全链固定中文出稿;需要英文时由 translate_en.py 翻译成稿(make_plans 里会问)——
# LANG 常量保留:make_report.py 的中英标签字典按它选择;
# _OUT_LANG 字符串不可改动——它参与 A 步缓存指纹,改一个字缓存全部失效
LANG = "zh"
_OUT_LANG = "所有生成的文字(字段值、正文、理由)一律用中文。"

# ——各站温度:发散步高温、判别步低温、写作步中温——
TEMP_A = 0.2         # A 忠实抽取(goal_gen 各判别步也用它)
TEMP_B = 0.8         # B 发散对比(全链最高)
TEMP_C = 0.4         # C/D 收敛成目标与扩写
TEMP_DESIGN = 0.4    # design 站:分解/扩写/修订
TEMP_OVERVIEW = 0.4  # overview 站:两节生成与修订

MAX_REFLECT_ROUNDS = 2   # overview 反思→修订轮数上限
