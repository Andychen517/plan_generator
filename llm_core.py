# -*- coding: utf-8 -*-
"""
LLM 基础设施 —— 全链唯一的地基,只此一份

各站(goal_gen / overview_gen / design_gen / translate_en)共用:
  MODEL / CLIENT   模型与客户端(读 .env.local 的 OPENAI_KEY / OPENAI_ENDPOINT / CUSTOM_MODEL)
  call_llm         带重试的调用入口(自动把输出语言指令追加进系统提示)
  parse_json       容错 JSON 解析(对付 r1 思维块 / 代码围栏)
  dump             中间结果存盘(output/*.json)
  OUT_DIR          全链共用输出目录
  set_out_lang     切换输出语言指令(仅 translate_en 出英文稿时用)

约定:本文件只放"怎么调模型"的工程函数,不放任何业务逻辑与提示词。
"""

import os
import re
import json
import time
from pathlib import Path

from openai import OpenAI

from config import _OUT_LANG as _DEFAULT_OUT_LANG

__all__ = ["REPO_ROOT", "OUT_DIR", "MODEL", "CLIENT",
           "call_llm", "parse_json", "dump", "set_out_lang"]

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = Path(__file__).resolve().parent / "output"
OUT_DIR.mkdir(exist_ok=True)

# 读 .env.local:先找 plan_gen 自己目录(独立分发/朋友测试),再找仓库根(原有布局)
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

# 运行期输出语言指令:默认取 config._OUT_LANG(全链中文出稿)。
# translate_en 出英文稿前用 set_out_lang 覆盖;A 步缓存指纹始终用 config 原值,不受覆盖影响。
_OUT_LANG = _DEFAULT_OUT_LANG


def set_out_lang(instruction: str) -> None:
    """覆盖 call_llm 追加的输出语言指令(translate_en 专用,其余场景勿用)。"""
    global _OUT_LANG
    _OUT_LANG = instruction


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
