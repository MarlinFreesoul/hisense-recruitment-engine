"""
海信 AI 招聘智能体 · JD 生成器
==============================
JD = 岗位族模板（固定骨架）+ 岗位参数（可变，HR/用人部门可改）→ 渲染成结构化 JD（四字段）。

四字段：任职要求(硬) / 技能模型 / 经验门槛 / 软实力。
骨架来自 job_families_v2.json，参数由调用方传入，LLM 只在「从岗位需求描述提炼参数」时介入。
"""
from __future__ import annotations
import json
import pathlib
from typing import Any

BASE = pathlib.Path(__file__).resolve().parent.parent


def load_family(key: str) -> dict:
    families = json.loads((BASE / "job_families_v2.json").read_text(encoding="utf-8"))["job_families"]
    for f in families:
        if f["key"] == key:
            return f
    raise KeyError(f"未找到岗位族：{key}（可选：{', '.join(f['key'] for f in families)}）")


def generate_jd(family_key: str, params: dict) -> dict:
    """模板渲染 + 参数 → 结构化 JD。

    params 可含：position(岗位名)、location(地点)、salary(薪资)、
                extra_hard(补充硬条件)、extra_skills(补充技能)、extra_resp(职责)。
    """
    fam = load_family(family_key)
    sm = fam.get("skill_model", {})
    jd = {
        "jd_id": params.get("jd_id", "JD-AUTO"),
        "position": params.get("position", fam["representative"][0]),
        "job_family": fam["name"],
        "location": params.get("location", "佛山顺德"),
        "salary": params.get("salary", fam.get("salary_band", "")),
        "requirements_hard": fam.get("hard_filters", []) + params.get("extra_hard", []),
        "skill_model": {
            "required": sm.get("required", []) + params.get("extra_skills", []),
            "preferred": sm.get("preferred", []),
        },
        "experience_threshold": params.get("experience", fam.get("experience_threshold", {"min_years": 0})),
        "soft_qualities": params.get("soft_qualities", fam.get("soft_qualities", [])),
        "responsibilities": params.get("responsibilities", []),
        "domain_sub_disciplines": fam.get("sub_disciplines", []),  # 制造业垂直领域词库（冰箱研发细分）
        "_editable": True,  # PRD：HR/用人部门可修改调整
        "_template": family_key,
    }
    return jd


if __name__ == "__main__":
    jd = generate_jd("firstline", {"position": "装配包装工", "salary": "5000-6000元/月"})
    print(json.dumps(jd, ensure_ascii=False, indent=2))
