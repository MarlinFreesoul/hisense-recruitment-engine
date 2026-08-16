"""简历筛查节点(可解释匹配)— P0

输入:简历文本 + 岗位 JD(结构化)
输出:可解释的匹配结果(硬条件逐条 check + 软条件评分 + 短板),而非黑箱分数。

设计原则(针对 HackerRank 同一简历评分 66~99 波动的教训):
- 硬条件走确定性规则,不靠 LLM
- 软条件才用 LLM,且每条必须带证据
- 最终分数可逐项回溯,不是拍脑袋
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace


@dataclass
class HardRequirement:
    """一条硬性要求(学历/经验/年龄/技能等)。"""
    field: str            # 学历 / 经验 / 年龄 / 技能
    requirement: str      # 岗位要求文字,如 "本科"、"5年"、"STM32"
    matched: bool = False
    extracted: str = ""   # 从简历提取到的值
    evidence: str = ""    # 证据(简历原文片段)


@dataclass
class JobDescription:
    """结构化岗位 JD。"""
    title: str
    hard: list[HardRequirement] = field(default_factory=list)
    soft: list[str] = field(default_factory=list)   # 软性维度/关键词


@dataclass
class ScreeningResult:
    """可解释的筛查结果。"""
    hard_pass: bool
    hard_checks: list[HardRequirement]
    overall: float                  # 0-100
    gaps: list[str]                 # 短板(喂给面试模块出题)
    explanation: str


# ---- 字段抽取(规则版 v1,后续由 LLM 结构化节点替代) ----

_EDU_RANK = {
    "博士": 6, "硕士": 5, "研究生": 5, "本科": 4,
    "大专": 3, "中专": 2, "高中": 1, "初中": 0,
}


def _extract_education(text: str) -> tuple[str, int]:
    for lv, rank in sorted(_EDU_RANK.items(), key=lambda x: -x[1]):
        if lv in text:
            return lv, rank
    return "未识别", -1


def _extract_experience_years(text: str) -> int | None:
    m = re.search(r"(\d{1,2})\s*年", text)
    return int(m.group(1)) if m else None


def _check_hard(req: HardRequirement, text: str) -> HardRequirement:
    """逐条检查硬条件,返回带结果的新对象(不可变)。"""
    if req.field == "学历":
        lv, rank = _extract_education(text)
        need = _EDU_RANK.get(req.requirement, 4)  # 未识别默认按本科
        return replace(req, matched=rank >= need, extracted=lv, evidence=lv)

    if req.field == "经验":
        years = _extract_experience_years(text)
        m = re.search(r"\d+", req.requirement)
        need = int(m.group()) if m else 0
        ok = years is not None and years >= need
        return replace(
            req, matched=ok,
            extracted=f"{years}年" if years is not None else "未识别",
            evidence=f"{years}年" if years is not None else "无",
        )

    if req.field == "技能":
        kw = req.requirement
        ok = kw.lower() in text.lower()
        return replace(
            req, matched=ok, extracted=kw if ok else "缺失",
            evidence=kw if ok else "简历未提及",
        )

    # 未知字段:规则未覆盖,默认通过,交由 LLM 兜底
    return replace(req, matched=True, extracted="(LLM兜底)", evidence="规则未覆盖")


def _score_soft(text: str, soft_dims: list[str]) -> float:
    """软条件 v1:关键词命中率(0~1)。后续接 LLM 评分 + 证据。"""
    if not soft_dims:
        return 1.0
    hit = sum(1 for d in soft_dims if d.lower() in text.lower())
    return hit / len(soft_dims)


def screen(resume_text: str, jd: JobDescription) -> ScreeningResult:
    """筛查节点入口:简历文本 × JD → 可解释匹配结果。"""
    checks = [_check_hard(req, resume_text) for req in jd.hard]
    hard_pass = all(c.matched for c in checks)

    hard_ratio = sum(1 for c in checks if c.matched) / len(checks) if checks else 1.0
    soft_ratio = _score_soft(resume_text, jd.soft)
    overall = round(hard_ratio * 70 + soft_ratio * 30, 1)

    gaps = [
        f"{c.field}:要求{c.requirement},简历={c.extracted or '缺失'}"
        for c in checks if not c.matched
    ]

    failed = "、".join(
        f"{c.field}({c.requirement})" for c in checks if not c.matched
    ) or "无"
    explanation = (
        f"硬条件{'全部通过' if hard_pass else '不通过:' + failed};"
        f"软条件命中率 {soft_ratio:.0%};总分 {overall}/100"
    )

    return ScreeningResult(
        hard_pass=hard_pass,
        hard_checks=checks,
        overall=overall,
        gaps=gaps,
        explanation=explanation,
    )


if __name__ == "__main__":
    jd = JobDescription(
        title="嵌入式高级软件开发工程师",
        hard=[
            HardRequirement("学历", "本科"),
            HardRequirement("经验", "5年"),
            HardRequirement("技能", "STM32"),
            HardRequirement("技能", "C语言"),
        ],
        soft=["嵌入式", "制冷", "PCB", "ARM"],
    )
    resume = (
        "张三,28岁,硕士。5年嵌入式开发经验,精通C语言、STM32、ARM,做过冰箱主控板开发。"
    )
    r = screen(resume, jd)
    print(jd.title)
    print(r.explanation)
    for c in r.hard_checks:
        mark = "✅" if c.matched else "❌"
        print(f"  [{c.field}] {c.requirement} → {mark} ({c.extracted})")
    print("短板:", r.gaps)
