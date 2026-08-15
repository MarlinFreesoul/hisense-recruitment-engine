"""
海信 AI 招聘智能体 · 风险识别（确定性规则版）
============================================
覆盖简历可判的风险：工作断层、频繁跳槽、证书过期。
简历判不了的（造假、技能真实性）留给面试 STAR + 背调。
"""
from __future__ import annotations
from typing import Any


def _latest_years(work: list[dict]) -> float:
    return float(work[0].get("duration_years", 0)) if work else 0.0


def detect_risks(resume: dict) -> list[dict]:
    risks = []
    work = resume.get("work_experience", [])
    edu = resume.get("education", {})
    certs = resume.get("certificates", [])
    expected = resume.get("expected", {})

    # 1. 工作断层：教育结束 vs 第一份工作开始（粗判）
    #    这里用「经历之间是否有 gap」的简化代理：工作段数 > 0 且最近一段 < 0.5 年
    if work and _latest_years(work) < 0.5:
        risks.append({"type": "稳定性", "level": "中", "detail": "最近一段工作 < 6 个月，需确认是否在岗或断层"})

    # 2. 频繁跳槽：段数 >= 3 且平均每段 < 1 年
    if len(work) >= 3:
        avg = sum(float(w.get("duration_years", 0)) for w in work) / len(work)
        if avg < 1:
            risks.append({"type": "频繁跳槽", "level": "中", "detail": f"{len(work)} 段工作，平均每段 {avg:.1f} 年"})

    # 3. 证书过期：证书无有效期标注
    for c in certs:
        if not c.get("expiry") or c.get("expiry") in ("未注明", "", None):
            risks.append({"type": "证书核验", "level": "中", "detail": f"证书「{c.get('name')}」未注明有效期，需核验"})

    # 4. 期望错位：求职意向与目标岗位不一致（留存的代理信号）
    intention = expected.get("career_intention", "")
    target = expected.get("target_position", "")
    if intention and target and intention not in target:
        # 例：意向「生产管理方向」vs 目标「装配包装工」
        risks.append({"type": "期望错位", "level": "中",
                      "detail": f"求职意向「{intention}」与目标岗位「{target}」存在落差，留存风险"})

    if not risks:
        risks.append({"type": "无", "level": "低", "detail": "简历层面未发现可判风险点"})

    return risks


def risk_report(resume: dict) -> dict:
    risks = detect_risks(resume)
    levels = {"低": 1, "中": 2, "高": 3}
    overall = max((levels.get(r["level"], 1) for r in risks), default=1)
    return {
        "risks": risks,
        "overall_level": {1: "低", 2: "中", 3: "高"}[overall],
        "deferred_to": ["面试 STAR 追问（造假/技能真实性）", "背调（证书/犯罪/断层核实）", "体检（健康）"],
    }


if __name__ == "__main__":
    import json, pathlib
    base = pathlib.Path(__file__).resolve().parent.parent
    resume = json.loads((base / "sample_resume.json").read_text(encoding="utf-8"))
    print(json.dumps(risk_report(resume), ensure_ascii=False, indent=2))
