"""
陈老师 demo 数据聚合接口
========================
把飞书真实数据（JD + 简历 + 评分）聚合成陈老师 demo（hr_workbench.html）需要的数据格式。
候选人按「应聘岗位」绑定岗位，只对匹配岗位评分 + 生成一套面试题，不再重复。
"""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from matcher_v2 import FeishuClient, feishu_to_resume, score_feishu_resume, match_job_family
from jd_generator import load_family
from interview_collect import generate_core_questions
from config import JD_TABLE_ID, RESUME_TABLE_ID, INTERNAL_TALENT_TABLE_ID, HISTORICAL_TALENT_TABLE_ID

# 面试题的期望信号/风险信号（按维度动态生成，不再写死）
QUESTION_SIGNALS = {
    "倒班接受": ("能接受倒班并说明过往倒班经历", "回答含糊或拒绝倒班"),
    "到岗时间": ("给出明确到岗日期和交接安排", "到岗时间反复变化"),
    "证书核验": ("能提供证书原件和有效期", "无法提供或含糊"),
    "期望落差": ("说明真实求职意向", "回避或前后矛盾"),
    "稳定性": ("说明长期稳定承诺", "回避离职原因"),
    "沟通": ("举例说明沟通协调场景", "空泛无实例"),
    "抗压": ("举例说明抗压经历", "回避压力场景"),
    "团队协作": ("举例说明协作经历", "空泛无实例"),
}


# ============ 模块4：人才评价汇总 ============
def _talent_internal_item(fields):
    return {
        "name": fields.get("姓名", ""),
        "current_role": fields.get("当前岗位", ""),
        "department": fields.get("部门", ""),
        "skills": fields.get("技能", ""),
        "availability": fields.get("可到岗", ""),
        "match_score": int(float(fields.get("匹配度") or 0)),
        "reason": fields.get("推荐理由", ""),
        "risk": fields.get("风险", ""),
        "action": fields.get("动作", ""),
    }


def _talent_historical_item(fields):
    return {
        "name": fields.get("姓名", ""),
        "previous_job": fields.get("曾应聘岗位", ""),
        "interview_result": fields.get("面试结果", ""),
        "offer_status": fields.get("offer状态", ""),
        "no_show_reason": fields.get("未到岗原因", ""),
        "skills": fields.get("技能", ""),
        "match_score": int(float(fields.get("匹配度") or 0)),
        "reason": fields.get("理由", ""),
        "risk": fields.get("风险", ""),
        "action": fields.get("动作", ""),
    }


def build_talent_sources(feishu, jobs):
    """人才来源优先级：内部人才库 → 历史候选人 → 外招（每岗位取 top3）。"""
    internal = feishu.get_records(INTERNAL_TALENT_TABLE_ID)
    historical = feishu.get_records(HISTORICAL_TALENT_TABLE_ID)
    result = []
    for job in jobs:
        title = job["job_title"]
        int_matches = [r["fields"] for r in internal if title in (r["fields"].get("可调岗岗位", "") or "")]
        int_matches.sort(key=lambda f: -float(f.get("匹配度") or 0))
        hist_matches = [r["fields"] for r in historical if title in (r["fields"].get("目标岗位", "") or "")]
        hist_matches.sort(key=lambda f: -float(f.get("匹配度") or 0))
        result.append({
            "job_id": job["job_id"],
            "job_title": title,
            "internal": [_talent_internal_item(f) for f in int_matches[:3]],
            "historical": [_talent_historical_item(f) for f in hist_matches[:3]],
            "external_count": 0,  # 由 build_demo_data 回填外招简历数
        })
    return result


def build_comparisons(screening_results, jobs):
    """候选人对比：每岗位 top（推荐）与 backup（待确认），对比维度对齐 V2。"""
    result = []
    for job in jobs:
        jr = [s for s in screening_results if s["target_job_id"] == job["job_id"]]
        top = [s for s in jr if s["screening_status"] == "推荐"]
        backup = [s for s in jr if s["screening_status"] == "待确认"]
        def _cmp_item(s):
            return {
                "candidate_name": s.get("candidate_id", ""),
                "match_score": s.get("match_score", 0),
                "screening_status": s.get("screening_status", ""),
                "risk_warnings": [r.get("risk_type", "") for r in s.get("risk_warnings", [])],
                "dimension_scores": s.get("dimension_scores", []),
            }
        result.append({
            "job_id": job["job_id"],
            "job_title": job["job_title"],
            "comparison_dimensions": ["综合匹配分", "岗位核心经验", "风险核验点", "到岗/稳定性", "面试重点"],
            "top_candidates": [_cmp_item(s) for s in top[:5]],
            "backup_candidates": [_cmp_item(s) for s in backup[:5]],
        })
    return result


def build_talent_pool(screening_results, jobs):
    """入库 + offer 递补：合格集（推荐+待确认）按分数排序，排除 offer 放弃者后给出递补顺序。"""
    result = []
    for job in jobs:
        jr = [s for s in screening_results if s["target_job_id"] == job["job_id"]]
        qualified = [s for s in jr if s["screening_status"] in ("推荐", "待确认")]
        qualified.sort(key=lambda s: -(s.get("match_score") or 0))
        def _pool_item(s):
            return {
                "candidate_name": s.get("candidate_id", ""),
                "match_score": s.get("match_score", 0),
                "screening_status": s.get("screening_status", ""),
                "decision_summary": s.get("decision_summary", ""),
                "risk_warnings": [r.get("risk_type", "") for r in s.get("risk_warnings", [])],
            }
        result.append({
            "job_id": job["job_id"],
            "job_title": job["job_title"],
            "qualified": [_pool_item(s) for s in qualified],
            "replacement_order": [_pool_item(s) for s in qualified[1:6]],  # 模拟 offer 放弃首名后递补
        })
    return result


def _job_to_demo(jd_record, index, family):
    fields = jd_record["fields"]
    return {
        "job_id": f"JOB-{index:03d}",
        "job_title": fields.get("岗位名称", ""),
        "job_family": family["name"],
        "department": fields.get("需求部门", "") or "容声冰箱制造中心",
        "location": fields.get("城市", "") or "佛山顺德",
        "headcount": fields.get("需求人数", 0) or 0,
        "salary_range": family.get("salary_band", ""),
        "urgency": "常规招聘",
        "dimensions": [{"name": d["dim"], "weight": round(d.get("weight", 0) * 100)} for d in family.get("soft_scores", [])],
        "hard_requirements": [f["dim"] for f in family.get("hard_filters", [])],
        "soft_requirements": [],
        "jd_summary": fields.get("岗位描述", "")[:100] or f"{fields.get('岗位名称', '')}，常规招聘。",
    }


def _resume_to_pool(resume_record, index):
    fields = resume_record["fields"]
    return {
        "candidate_id": f"POOL-CAND-{index:03d}",
        "candidate_name": fields.get("姓名", ""),
        "target_job_id": "",
        "batch_id": "BATCH-REAL",
        "age_range": fields.get("年龄", "") or "",
        "education": fields.get("最高学历", "") or "",
        "major": fields.get("专业", "") or "",
        "work_years": fields.get("工作年限", 0) or 0,
        "current_location": fields.get("当前地点", "") or "",
        "expected_salary": fields.get("期望薪资", "") or "",
        "availability": fields.get("期望到岗", "") or "",
        "job_intention": fields.get("应聘岗位", "") or "",
        "skills": fields.get("核心技能", []) or [],
        "certificates": (fields.get("证书", "") or "").split("、") if fields.get("证书") else [],
        "risk_signals": [],
    }


def _merge_risk_warnings(risk_warnings):
    """合并同类风险：多个「证书核验」合并成一条。"""
    cert_risks = [w for w in risk_warnings if w.get("risk_type") == "证书核验"]
    other_risks = [w for w in risk_warnings if w.get("risk_type") != "证书核验"]
    merged = []
    if cert_risks:
        cert_names = []
        for w in cert_risks:
            ev = w.get("evidence", "")
            if "「" in ev:
                cert_names.append(ev.split("「")[1].split("」")[0])
        merged.append({
            "risk_type": "证书核验",
            "risk_level": cert_risks[0].get("risk_level", "中"),
            "evidence": f"证书「{'、'.join(cert_names)}」未注明有效期，需核验" if cert_names else "证书有效期未注明",
            "suggested_verify_question": "请核验证书原件与有效期",
        })
    merged.extend(other_risks)
    return merged


def build_demo_data():
    feishu = FeishuClient()
    jd_records = [r for r in feishu.get_records(JD_TABLE_ID) if r["fields"].get("岗位名称")]
    resume_records = [r for r in feishu.get_records(RESUME_TABLE_ID) if r["fields"].get("姓名")]

    # 建立 岗位名 → job_id 映射
    job_name_to_id = {}
    jobs = []
    for i, jd in enumerate(jd_records, 1):
        job_name = jd["fields"].get("岗位名称", "")
        family_key = match_job_family(job_name)
        if family_key is None:
            continue
        family = load_family(family_key)
        job_id = f"JOB-{i:03d}"
        job_name_to_id[job_name] = job_id
        jobs.append(_job_to_demo(jd, i, family))

    resume_pool = []
    screening_results = []
    interview_questions = []

    for j, r in enumerate(resume_records, 1):
        candidate_id = f"POOL-CAND-{j:03d}"
        target_job_name = r["fields"].get("应聘岗位", "") or ""
        target_job_id = job_name_to_id.get(target_job_name, "")

        pool_item = _resume_to_pool(r, j)
        pool_item["target_job_id"] = target_job_id
        resume_pool.append(pool_item)

        if not target_job_id:
            continue

        family_key = match_job_family(target_job_name)
        family = load_family(family_key)
        resume = feishu_to_resume(r["fields"])
        score = score_feishu_resume(resume, family)

        # 转换 dimension_scores 到陈老师体系：weight 0-1 → 满分(0-100)，score 0-10 → 得分(0-100)
        demo_dims = []
        for d in score["dimension_scores"]:
            w100 = round(d["weight"] * 100)
            s100 = round(d["score"] * d["weight"] * 10)
            demo_dims.append({
                "dimension_name": d["dimension_name"], "weight": w100,
                "score": s100, "evidence": d["evidence"], "deduction_reason": d["deduction_reason"],
            })

        screening_results.append({
            "candidate_id": candidate_id,
            "target_job_id": target_job_id,
            "screening_status": score["screening_status"],
            "match_score": score["match_score"],
            "next_action": score.get("next_action", ""),
            "decision_summary": score["decision_summary"],
            "recommend_reasons": score["recommend_reasons"],
            "pending_reasons": score["pending_reasons"],
            "reject_reasons": score["reject_reasons"],
            "risk_warnings": _merge_risk_warnings(score["risk_warnings"]),
            "dimension_scores": demo_dims,
        })

        # 面试题：每个候选人一套，priority 从 1 递增（每个候选人独立编号）
        qs = generate_core_questions(family_key, resume, score.get("风险点", []))
        for qi, q in enumerate(qs, 1):
            expected, risk = QUESTION_SIGNALS.get(q["维度"], ("给出明确回答", "回答含糊"))
            interview_questions.append({
                "question_id": f"Q-{candidate_id}-{q['id']}",
                "candidate_id": candidate_id,
                "target_job_id": target_job_id,
                "question_group": "硬条件核验" if q["维度"] in ("倒班接受", "到岗时间", "证书核验") else "素质追问",
                "question_type": "hard_check",
                "main_question": q["问题"],
                "question_text": q["问题"],
                "follow_ups": [],
                "why_ask": f"核验{q['维度']}" if q["维度"] != "证书核验" else "核验证书有效期",
                "question_reason": f"核验{q['维度']}" if q["维度"] != "证书核验" else "核验证书有效期",
                "expected_signal": expected,
                "risk_signal": risk,
                "priority": qi,
            })

    # 按分数排序给 rank
    screening_results.sort(key=lambda x: x["match_score"] or 0, reverse=True)
    for idx, s in enumerate(screening_results, 1):
        s["rank"] = idx

    total = len(screening_results)
    recommend = sum(1 for s in screening_results if s["screening_status"] == "推荐")
    pending = sum(1 for s in screening_results if s["screening_status"] == "待确认")
    reject = sum(1 for s in screening_results if s["screening_status"] == "不推荐")
    summary = [
        {"metric": "总数", "value": total},
        {"metric": "推荐", "value": recommend},
        {"metric": "待确认", "value": pending},
        {"metric": "不推荐", "value": reject},
    ]

    # 模块4：人才评价汇总（人才来源优先级 / 候选人对比 / 入库 + offer 递补）
    talent_sources = build_talent_sources(feishu, jobs)
    for ts in talent_sources:
        # 回填外招简历数（该岗位应聘的简历数）
        ts["external_count"] = sum(1 for r in resume_records if r["fields"].get("应聘岗位") == ts["job_title"])
    comparisons = build_comparisons(screening_results, jobs)
    talent_pool = build_talent_pool(screening_results, jobs)

    return {
        "jobs": jobs,
        "resume_pool": resume_pool,
        "screening_results": screening_results,
        "interview_questions": interview_questions,
        "summary": summary,
        "talent_sources": talent_sources,
        "candidate_comparisons": comparisons,
        "talent_pool": talent_pool,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(build_demo_data(), ensure_ascii=False, indent=2))
