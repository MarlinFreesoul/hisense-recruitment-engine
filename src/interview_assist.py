"""
视频面试 · 实时辅助（复用 DeepSeek）
=================================
基于面试实时转写文本 + 岗位族 + 风险点，调用 DeepSeek 给面试官生成：
  - 建议追问（结合题库与已聊内容，避免重复发问）
  - 风险预警（如候选人提到频繁跳槽 / 离职原因模糊 / 倒班意愿摇摆）
  - STAR 追问提示

完全复用现有 DEEPSEEK 配置与调用方式；延续项目「安全护栏」原则：
不生成任何涉及婚育 / 民族 / 健康史等非岗位必要信息的提问。
"""
from __future__ import annotations
import json
import re

import requests

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from src.interview import load_question_bank  # 复用现有题库


def _load_baseline_questions(family_key: str) -> list:
    """从现有题库取该岗位族的结构化问题，作为辅助上下文。"""
    try:
        bank = load_question_bank()
    except Exception:
        return []
    entry = next((b for b in bank.get("banks", []) if b["key"] == family_key), None)
    if not entry:
        return []
    return [{"维度": d.get("dim"), "问题": d.get("q")} for d in entry.get("dimensions", [])]


def suggest_assist(transcript: str, family_key: str, risk_points: list = None,
                   last_question: str = "", api_key: str = None) -> dict:
    """根据当前转写文本，返回实时辅助建议。

    transcript   : 截至当前的面试对话转写（越精炼越好，建议只传最近若干轮）
    family_key   : 岗位族 key（如 firstline / process-equipment）
    risk_points  : 简历风险点列表（来自 risk_filter.risk_report）
    last_question: 上一轮面试官已问的问题，避免重复
    """
    key = api_key or DEEPSEEK_API_KEY
    if not key:
        raise ValueError("未配置 DEEPSEEK_API_KEY，无法生成实时辅助")

    baseline = _load_baseline_questions(family_key)
    baseline_txt = "\n".join(f"- [{q['维度']}] {q['问题']}" for q in baseline if q.get("问题")) or "（无）"
    risk_txt = "\n".join(f"- {r.get('type', '')}: {r.get('detail', '')}" for r in (risk_points or [])) or "（无）"

    prompt = f"""你是制造业招聘的「面试辅助官」，正在一场视频面试的现场，实时给面试官提建议。
当前候选人应聘岗位族：{family_key}
简历已识别的风险点：
{risk_txt}

该岗位族的标准结构化问题（仅供参考，别简单复述）：
{baseline_txt}

最近一轮面试官已问：{last_question or '（暂无）'}

截至当前的面试对话转写：
---
{transcript[-2000:]}
---

请输出 JSON（不要其他内容）：
{{
  "建议追问": "结合已聊内容、针对岗位关键能力或某个未澄清的风险点，给出一句具体可问的话",
  "风险预警": "若转写中出现频繁跳槽/离职模糊/倒班意愿摇摆/技能夸大等信号，给一句提醒；若无则填空字符串",
  "STAR提示": "若候选人给笼统回答，提示面试官用 STAR 法追问的一句话；否则填空字符串"
}}

约束：绝不生成涉及婚育、民族、健康史、宗教信仰等非岗位必要信息的提问。只输出中文。"""

    resp = requests.post(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": DEEPSEEK_MODEL, "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.3, "response_format": {"type": "json_object"}},
        timeout=30,
    )
    data = resp.json()
    if "choices" not in data:
        raise Exception(f"辅助 LLM 调用失败: {data}")
    content = data["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.DOTALL)
        return json.loads(m.group()) if m else {"建议追问": "", "风险预警": "", "STAR提示": ""}


if __name__ == "__main__":
    import sys
    sample = sys.argv[1] if len(sys.argv) > 1 else "面试官：你上一份工作做了多久？候选人：其实我这两年换了三家公司。"
    print(json.dumps(suggest_assist(sample, "firstline", [{"type": "频繁跳槽", "detail": "近两年3段经历"}], ""),
                     ensure_ascii=False, indent=2))
