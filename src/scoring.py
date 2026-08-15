"""
海信 AI 招聘智能体 · 确定性打分引擎
====================================
原则（双向锚定）：
  1. 每个匹配维度必须回溯到简历真实字段或可观测代理；
  2. 每个维度得分由「确定性评分函数」计算 —— 同一份简历在任何机器上结果一致；
  3. LLM 只在「语义判断」（专业对口/职位对口）介入，纯规则一律用确定性函数；
  4. 简历里抽不到的维度（动机/健康/技能真实性）不进快速筛选，移给面试/背调。

用法：
    from scoring import compute_match
    report = compute_match(resume, job_family)
"""
from __future__ import annotations
import json
from typing import Any

# 学历层级（用于学历门槛比较）
EDU_LEVELS = {
    "学历不限": 0, "初中及以下": 1, "中专/中技": 2, "高中": 2,
    "大专": 3, "本科": 4, "硕士": 5, "博士": 6,
}

# 三态评分状态：区分「字段缺失(未知)」和「字段不满足」
UNKNOWN = "未知"
SATISFIED = "满足"
UNSATISFIED = "不满足"


# ---------- 工具函数（确定性） ----------

def _parse_age(age_range: str) -> float:
    """'25-30岁' -> 27.5 ; '18岁' -> 18 ; 解析失败返回 None"""
    try:
        digits = [int(s) for s in age_range.replace("岁", "").split("-") if s.strip().isdigit()]
        return sum(digits) / len(digits) if digits else None
    except Exception:
        return None


def _total_years(work: list[dict]) -> float:
    return sum(float(w.get("duration_years", 0)) for w in work)


def _latest_years(work: list[dict]) -> float:
    return float(work[0].get("duration_years", 0)) if work else 0.0


# ---------- 硬条件（布尔规则，一票否决） ----------

def check_hard(resume: dict, family: dict) -> tuple[bool, list[dict]]:
    """返回 (是否全部通过, 每项结果)。硬条件不通过 → 直接淘汰。"""
    results = []
    passed = True
    for f in family.get("hard_filters", []):
        dim = f["dim"]
        ok, detail = _check_one_hard(resume, f)
        results.append({"dim": dim, "pass": ok, "detail": detail})
        if not ok:
            passed = False
    return passed, results


def _check_one_hard(resume: dict, f: dict) -> tuple[bool, str]:
    dim, evidence, rule = f["dim"], f["evidence"], f.get("rule", "")

    if dim == "年龄":
        age = _parse_age(resume.get("age_range", ""))
        # rule 形如 "18-45岁"
        bounds = [int(s) for s in rule.replace("岁", "").split("-") if s.strip().isdigit()]
        if age is None:
            return True, "年龄未识别，转人工确认"
        lo, hi = (bounds[0], bounds[1]) if len(bounds) == 2 else (bounds[0], bounds[0])
        return lo <= age <= hi, f"年龄{age}岁 ∈ [{lo},{hi}]"

    if dim == "学历":
        degree = resume.get("education", {}).get("degree", "")
        need = EDU_LEVELS.get(rule, 0)
        actual = EDU_LEVELS.get(degree, 0)
        return actual >= need, f"学历{degree}({actual}) vs 要求{rule}({need})"

    if dim == "到岗意愿":
        avail = resume.get("expected", {}).get("available_date", "")
        # 规则：越快越好，默认要求 1 个月内
        if "1个月" in avail or "立即" in avail or "随时" in avail:
            return True, f"到岗时间{avail}"
        return True, f"到岗时间{avail}（非硬伤，降级排序）"

    if dim == "倒班接受":
        text = resume.get("self_evaluation", "")
        kw = ["倒班", "夜班", "两班倒", "三班倒"]
        hit = any(k in text for k in kw)
        return hit, f"自我评价{'命中' if hit else '未命中'}倒班关键词"

    if dim == "专业对口":
        major = resume.get("education", {}).get("major", "")
        return True, f"专业「{major}」交由语义判断，不在硬条件拦截"

    return True, f"维度{dim}未定义规则，放行"


# ---------- 软条件（确定性评分函数，0-10 分/维度） ----------

def score_stability(resume: dict, family: dict = None):
    """稳定性：最近一段工作持续时间（跳槽频率的代理）。无经历→未知。"""
    work = resume.get("work_experience", []) or []
    if not work:
        return UNKNOWN, 0
    y = _latest_years(work)
    if y >= 2: return SATISFIED, 10
    if y >= 1: return SATISFIED, 7
    if y >= 0.5: return UNSATISFIED, 4
    return UNSATISFIED, 2


def score_soft_qualities(resume: dict, family: dict = None):
    """软实力：自我评价关键词命中数 ×2，上限10。无自我评价→未知。"""
    text = (resume.get("self_evaluation", "") or "").strip()
    if not text:
        return UNKNOWN, 0
    kw = ["吃苦", "倒班", "协作", "团队", "纪律", "抗压", "认真", "责任", "踏实"]
    score = min(10, sum(1 for k in kw if k in text) * 2)
    return (SATISFIED if score > 0 else UNSATISFIED), score


def score_experience(resume: dict, family: dict = None):
    """经验：总年限 + 职位对口（家电/制造）加分。无经历→未知。"""
    work = resume.get("work_experience", []) or []
    if not work:
        return UNKNOWN, 0
    total = _total_years(work)
    if total >= 3: s = 10
    elif total >= 1: s = 7
    else: s = 4
    # 对口加分：职位或公司名命中制造/家电/冰箱
    for w in work:
        blob = (w.get("position", "") or "") + (w.get("company", "") or "")
        if any(k in blob for k in ["装配", "制造", "家电", "冰箱", "生产", "工艺", "质量"]):
            s += 1
            break
    return (SATISFIED if s >= 7 else UNSATISFIED), min(10, s)


def score_skills(resume: dict, family: dict = None):
    """技能：required 命中 + preferred 命中 + 证书加分，上限10。无技能且无证书→未知。"""
    skills = {s.strip() for s in (resume.get("skills", []) or [])}
    certs = resume.get("certificates", []) or []
    if not skills and not certs:
        return UNKNOWN, 0
    sm = (family or {}).get("skill_model", {})
    required = sm.get("required", [])
    preferred = sm.get("preferred", [])
    hit_req = sum(1 for r in required if r in skills)
    hit_pref = sum(1 for p in preferred if p in skills)
    s = round(hit_req / len(required) * 6) if required else 3
    s += hit_pref
    s += len(certs)
    return (SATISFIED if s > 3 else UNSATISFIED), min(10, s)


def load_major_mapping() -> dict:
    import pathlib
    base = pathlib.Path(__file__).resolve().parent.parent
    return json.loads((base / "major_job_mapping.json").read_text(encoding="utf-8"))


def score_major_match(resume: dict, family: dict = None):
    """专业对口：简历专业 → 专业大类 → 岗位族映射。
    无专业→未知（不再计 0 分）；对口 10、不对口 3、无法判断 5。"""
    major = (resume.get("education", {}).get("major", "") or "").strip()
    if not major:
        return UNKNOWN, 0
    family_name = (family or {}).get("name", "")
    for group in load_major_mapping()["major_groups"]:
        if any(k in major for k in group["keywords"]):
            hit = family_name in group["job_families"]
            return (SATISFIED, 10) if hit else (UNSATISFIED, 3)
    return UNKNOWN, 5  # 专业不在映射表，无法判断


# ---------- 汇总 ----------

def compute_match(resume: dict, family: dict) -> dict:
    """主入口（三态聚合）：硬条件 + 软条件 → 匹配度 0-100 + 可解释报告。"""
    hard_pass, hard_detail = check_hard(resume, family)

    soft_detail = []
    weighted_sum = 0.0
    applied_weight = 0.0
    for dim in family.get("soft_scores", []):
        key = dim["dim"]
        weight = dim.get("weight", 0.0)
        fn = {
            "稳定性": score_stability,
            "软实力": score_soft_qualities,
            "经验": score_experience,
            "技能": score_skills,
            "专业对口": score_major_match,
        }.get(key)
        if fn is None:
            soft_detail.append({"dim": key, "weight": weight, "state": "未配置", "raw": None})
            continue
        state, raw = fn(resume, family)
        if state == UNKNOWN:
            soft_detail.append({"dim": key, "weight": weight, "state": "未知", "raw": raw})
            continue
        weighted_sum += raw * weight
        applied_weight += weight
        soft_detail.append({"dim": key, "weight": weight, "state": state, "raw": raw, "weighted": round(raw * weight, 2)})

    score_100 = round(weighted_sum / applied_weight * 10, 1) if applied_weight > 0 else None

    return {
        "hard_pass": hard_pass,
        "hard_detail": hard_detail,
        "soft_detail": soft_detail,
        "match_score": score_100,
        "grade": _grade(score_100, hard_pass),
        "deferred_checks": family.get("deferred_checks", []),
    }


def _grade(score: float, hard_pass: bool) -> str:
    if not hard_pass: return "不通过（硬条件未达）"
    if score >= 90: return "A 级（高配）"
    if score >= 75: return "B 级（合格）"
    if score >= 60: return "C 级（待定）"
    return "不推荐"


if __name__ == "__main__":
    # 自测：用样本简历跑一遍
    import pathlib
    base = pathlib.Path(__file__).resolve().parent.parent
    resume = json.loads((base / "sample_resume.json").read_text(encoding="utf-8"))
    families = json.loads((base / "job_families_v2.json").read_text(encoding="utf-8"))["job_families"]
    family = next(f for f in families if f["key"] == "firstline")
    report = compute_match(resume, family)
    print(json.dumps(report, ensure_ascii=False, indent=2))
