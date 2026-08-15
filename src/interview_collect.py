"""
辅助面试 · 核心问题采集
========================
生成「HR 最关心的核心问题」（参数化：证书名、岗位名可替换），供 H5 表单采集。
硬指标（倒班/到岗/证书/期望/稳定性）+ 关键软条件（沟通/抗压/团队）。
不需要 LLM 对话，只要采集。
"""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jd_generator import load_family


def generate_core_questions(family_key: str, resume: dict, risk_points: list) -> list:
    """生成核心采集问题。不同岗位族 → 不同硬条件 → 问题自动不同；证书名从简历参数化。"""
    questions = []
    family = load_family(family_key)
    hard_dims = [f["dim"] for f in family.get("hard_filters", [])]

    # 硬指标：倒班、到岗
    if "倒班接受" in hard_dims:
        questions.append({"id": "shift", "维度": "倒班接受", "问题": "能接受两班倒/夜班吗？",
                          "类型": "单选", "选项": ["能接受", "不能接受", "视情况"]})
    if "到岗意愿" in hard_dims:
        questions.append({"id": "available", "维度": "到岗时间", "问题": "什么时候能到岗？",
                          "类型": "单选", "选项": ["立即", "1周内", "1个月内", "更久"]})

    # 证书（从 resume.certificates 参数化，每个证书一个问题）
    for cert in resume.get("certificates", []):
        name = cert.get("name", "证书")
        questions.append({"id": f"cert_{name}", "维度": "证书核验",
                          "问题": f"你的{name}有效期到什么时候？", "类型": "文本"})

    # 风险点：期望错位、频繁跳槽
    risk_types = [r.get("type", "") for r in risk_points]
    if any("期望错位" in t for t in risk_types):
        questions.append({"id": "expectation", "维度": "期望落差",
                          "问题": "你的求职意向和目标岗位有落差，能说说你的真实打算吗？", "类型": "文本"})
    if any(t in ("频繁跳槽", "稳定性") for t in risk_types):
        questions.append({"id": "stability", "维度": "稳定性",
                          "问题": "你之前换工作比较频繁，这次能保证做多久？", "类型": "文本"})

    # 关键软条件
    questions.append({"id": "communication", "维度": "沟通", "问题": "用一句话评价你的沟通协调能力",
                      "类型": "单选", "选项": ["强", "中", "弱"]})
    questions.append({"id": "pressure", "维度": "抗压", "问题": "你能接受多大强度的工作压力？",
                      "类型": "单选", "选项": ["强", "中", "弱"]})
    questions.append({"id": "teamwork", "维度": "团队协作", "问题": "你习惯团队协作还是独立完成任务？",
                      "类型": "单选", "选项": ["团队协作", "独立", "都可以"]})

    return questions


if __name__ == "__main__":
    resume = {"certificates": [{"name": "电工证", "expiry": "未注明"}, {"name": "钳工证", "expiry": "未注明"}]}
    qs = generate_core_questions("firstline", resume, [{"type": "证书核验"}, {"type": "期望错位"}])
    for q in qs:
        print(f"[{q['类型']}] {q['问题']}")
