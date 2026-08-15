"""
面试辅助模块
============
根据岗位族 + 候选人风险点，生成结构化面试题，写回飞书「面试记录」表。
确定性优先：题库（interview_question_bank.json）+ 风险点追问，LLM 可选增强。
"""
from __future__ import annotations
import json
import pathlib

BASE = pathlib.Path(__file__).resolve().parent.parent


def load_question_bank() -> dict:
    return json.loads((BASE / "interview_question_bank.json").read_text(encoding="utf-8"))


def generate_questions(family_key: str, resume: dict, risk_points: list) -> list:
    """生成面试题：题库基线 + 风险点追问。"""
    bank = load_question_bank()
    # 研发岗暂无独立题库，并入工艺设备类
    if family_key == "rnd-engineering":
        family_key = "process-equipment"
    entry = next((b for b in bank["banks"] if b["key"] == family_key), None)

    questions = []
    if entry:
        for dim in entry["dimensions"]:
            questions.append({"维度": dim["dim"], "问题": dim["q"], "追问": dim["probe"]})

    # 风险点定向追问
    for r in risk_points:
        t = r.get("type", "")
        if t == "证书核验":
            detail = r.get("detail", "")
            cert = detail.split("「")[1].split("」")[0] if "「" in detail else "证书"
            questions.append({"维度": "证书核验", "问题": f"你的{cert}有效期到什么时候？能提供原件核验吗？", "追问": ""})
        elif t == "期望错位":
            questions.append({"维度": "稳定性", "问题": "你的求职意向和目标岗位有落差，能说说真实打算吗？", "追问": "入职后如果短期内没有晋升机会，你能接受吗？"})
        elif t in ("频繁跳槽", "稳定性"):
            questions.append({"维度": "稳定性", "问题": "你之前换工作比较频繁，这次能保证做多久？", "追问": ""})
    return questions


def format_questions_text(questions: list) -> str:
    lines = []
    for i, q in enumerate(questions, 1):
        lines.append(f"{i}. [{q['维度']}] {q['问题']}")
        if q.get("追问"):
            lines.append(f"   追问：{q['追问']}")
    return "\n".join(lines)


def write_interview_record(feishu, candidate_name: str, job_name: str, questions: list) -> dict:
    """写飞书「面试记录」表：候选人 + 面试阶段 + 面试记录（生成的题目）。"""
    from config import INTERVIEW_TABLE_ID
    fields = {
        "候选人姓名": candidate_name,
        "面试阶段": "待面试",
        "面试记录": format_questions_text(questions),
    }
    # 面试记录表的字段可能有差异，只写通用字段
    return feishu.create_records(INTERVIEW_TABLE_ID, [fields])


if __name__ == "__main__":
    qs = generate_questions("firstline", {"name": "候选人A"}, [{"type": "证书核验", "detail": "证书「电工证」未注明有效期"}])
    print(format_questions_text(qs))
