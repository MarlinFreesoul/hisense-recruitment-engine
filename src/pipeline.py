"""
海信 AI 招聘智能体 · 漏斗编排（pipeline）
========================================
把「简历解析 → JD 生成 → 打分 → 风险 → 报告」串成一条可跑流程。
这是确定性代码层（算法层）；PromptX 角色通过 MCP 调用本层的语义判断点。
"""
from __future__ import annotations
import json
import pathlib
from .scoring import compute_match
from .risk_filter import risk_report
from .jd_generator import generate_jd, load_family
from .resume_parser import extract_text_from_pdf, parse_resume

BASE = pathlib.Path(__file__).resolve().parent.parent


def run_screening(resume_json: dict, family_key: str, jd_params: dict | None = None) -> dict:
    """核心漏斗：单份简历 → 结构化 → 打分 → 风险 → 可解释报告。

    单一数据源 = family（匹配逻辑结构）。
      - compute_match 用 family 匹配打分；
      - generate_jd   用 family 渲染展示 JD（四字段）。
    """
    family = load_family(family_key)
    jd = generate_jd(family_key, jd_params or {})
    match = compute_match(resume_json, family)
    risk = risk_report(resume_json)
    return {
        "resume": resume_json,
        "jd": jd,
        "match": match,
        "risk": risk,
        "recommendation": _recommend(match, risk),
    }


def run_batch(resumes: list[dict], family_key: str, jd_params: dict | None = None) -> dict:
    """批量：对 1000 份简历跑漏斗，输出 topK 排序。"""
    scored = []
    for r in resumes:
        result = run_screening(r, family_key, jd_params)
        if result["match"]["hard_pass"]:
            scored.append({"resume": r.get("name"), "match": result["match"], "risk": result["risk"]})
    scored.sort(key=lambda x: x["match"]["match_score"], reverse=True)
    return {"total": len(resumes), "passed": len(scored), "top": scored[:10]}


def _recommend(match: dict, risk: dict) -> str:
    if not match["hard_pass"]:
        return "淘汰（硬条件未达）"
    if risk["overall_level"] == "高":
        return "待定（高风险，建议人工复核）"
    if match["match_score"] >= 75:
        return "通过筛选 → 推送用人部门 → HR 电话初面"
    return "待定（匹配度不足）"


def main(resume_pdf_path: str, family_key: str = "firstline"):
    txt = extract_text_from_pdf(resume_pdf_path)
    if not txt:
        return {"error": "PDF 文本抽取为空，需 OCR 兜底（未接入）"}
    resume = parse_resume(txt)
    return run_screening(resume, family_key)


if __name__ == "__main__":
    import sys
    result = main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "firstline")
    print(json.dumps(result, ensure_ascii=False, indent=2))
