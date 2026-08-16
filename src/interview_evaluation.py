"""
视频面试 · 结构化评价（interviewEvaluation 契约）
==============================================
输入：带说话人标签的双人转写 + 岗位族 + 建议问题
复用 DeepSeek 抽取每个胜任力维度的 STAR 证据，映射为 0-10 维度分；
产出 interviewEvaluation：overallRating / dimensionScores / transcriptSummary /
hiringSuggestion / speakerTaggedTranscript / complianceFlags。

守护栏（延续项目原则）：
  - AI 仅辅助，不自动录用/淘汰；
  - 检测 HR 是否问婚育/民族/健康史/宗教信仰等非岗位必要问题（complianceFlags）；
  - 绝不基于上述敏感因素给分或建议。
"""
from __future__ import annotations
import json
import re

import requests

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from src.interview import load_question_bank


# 非岗位必要的敏感提问关键词（用于合规检测，不与评分挂钩）
_SENSITIVE_KW = ["婚育", "结婚", "生育", "怀孕", "二胎", "民族", "宗教信仰", "健康史",
                 "病史", "残疾", "乙肝", "血型", "户口", "籍贯", "生肖", "星座"]


def _dims_for_family(family_key: str) -> list:
    """取出该岗位族题库里的胜任力维度，作为面试评分维度。"""
    bank = load_question_bank()
    if family_key == "rnd-engineering":
        family_key = "process-equipment"
    entry = next((b for b in bank.get("banks", []) if b["key"] == family_key), None)
    if not entry:
        return []
    return [{"dim": d.get("dim"), "q": d.get("q")} for d in entry.get("dimensions", [])]


def detect_compliance(speaker_transcript: list, hr_speaker: str = None) -> list:
    """扫描转写，找出 HR 涉及敏感非岗位问题的片段。仅 HR 的发言计入。

    hr_speaker : 可选，显式指明哪一路是 HR（如 "说话人1" 或 TRTC 分轨录制时的 "hr"）。
                 生产里 HR 走已知轨道时传此值，合规检测不再依赖说话人分离是否分对人。
                 不传时按常见 HR 标识（HR/面试官/hr）匹配。
    """
    if hr_speaker is not None:
        hr_set = {hr_speaker}
    else:
        hr_set = {"HR", "面试官", "hr"}
    flags = []
    for s in speaker_transcript:
        if s.get("speaker") not in hr_set:
            continue
        txt = s.get("text", "")
        for kw in _SENSITIVE_KW:
            if kw in txt:
                flags.append(f"HR 提问涉及非岗位必要信息「{kw}」：{txt[:40]}")
                break
    return flags


def generate_evaluation(speaker_transcript: list, family_key: str,
                        suggested_questions: list = None, api_key: str = None,
                        hr_speaker: str = None) -> dict:
    """生成 interviewEvaluation。

    speaker_transcript : [{speaker, text, start, end}, ...]
    hr_speaker         : 可选，指明哪一路是 HR（见 detect_compliance）。
    返回 interviewEvaluation dict（含原始 speakerTaggedTranscript）。
    """
    key = api_key or DEEPSEEK_API_KEY
    if not key:
        raise ValueError("未配置 DEEPSEEK_API_KEY，无法生成面试评价")

    dims = _dims_for_family(family_key)
    dims_txt = "\n".join(f"- {d['dim']}（锚定标准问题：{d['q']}）" for d in dims) or "（无题库维度）"
    conv = "\n".join(f"{s.get('speaker','?')}：{s.get('text','')}" for s in speaker_transcript)
    hr_hint = f"\n注意：本场面试中「{hr_speaker}」是 HR/面试官，其余是候选人。" if hr_speaker else ""

    prompt = f"""你是制造业招聘的「面试评价官」。下面是一场视频面试的双人转写（已标注说话人）。
岗位族：{family_key}
该岗位族要评估的胜任力维度（锚定标准问题）：
{dims_txt}
{hr_hint}
转写全文：
---
{conv}
---

请输出 JSON（不要其他内容）：
{{
  "dimensionScores": [
    {{"dim":"维度名","score":0-10的整数,"state":"满足/不满足/未知","evidence":"引用转写中候选人原话或行为证据，最多30字"}}
  ],
  "overallRating": 0-10的浮点数,
  "transcriptSummary": "200字内面试纪要，含关键问答与结论",
  "hiringSuggestion": "仅给出「建议进入下一轮/待定/不建议」及理由，AI不替用人部门做最终录用或淘汰决定"
}}

约束：
1. dimensionScores 必须覆盖上面列出的每一个维度；
2. 评分必须有转写证据支撑，不得凭空给分；
3. 绝不基于婚育/民族/健康史/宗教信仰等非岗位因素给分或建议；
4. hiringSuggestion 只能给建议，不能替代最终决策。"""

    resp = requests.post(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": DEEPSEEK_MODEL, "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.2, "response_format": {"type": "json_object"}},
        timeout=60,
    )
    data = resp.json()
    if "choices" not in data:
        raise Exception(f"评价 LLM 调用失败: {data}")
    content = data["choices"][0]["message"]["content"]
    try:
        eval_obj = json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.DOTALL)
        eval_obj = json.loads(m.group()) if m else {}

    # 补上原始双人转写 + 合规检测（本地确定性，不依赖 LLM）
    eval_obj["speakerTaggedTranscript"] = speaker_transcript
    eval_obj["complianceFlags"] = detect_compliance(speaker_transcript, hr_speaker=hr_speaker)
    return eval_obj


if __name__ == "__main__":
    sample = [
        {"speaker": "HR", "text": "你上一份工作做了多久？为什么离开？", "start": 0, "end": 3},
        {"speaker": "候选人", "text": "我做了三年，因为想回老家发展。", "start": 3, "end": 7},
        {"speaker": "HR", "text": "能接受两班倒吗？", "start": 7, "end": 9},
        {"speaker": "候选人", "text": "可以，之前工厂也倒过班。", "start": 9, "end": 12},
    ]
    print(json.dumps(generate_evaluation(sample, "firstline"), ensure_ascii=False, indent=2))
