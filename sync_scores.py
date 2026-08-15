"""
把评分结果 + 面试题 + 招聘进度 完整写回飞书
============================================
与 demo_data.build_demo_data 使用同一套评分逻辑（按「应聘岗位」绑定岗位族），
把三条链路全部落到飞书，且**与前端展示字段一一对应，不留缺口**：

  1. 评分结果表   —— 101 份：匹配度/推荐结论/等级/风险等级/下一步动作/决策摘要/匹配总结/多行文本(维度+原因+风险)
  2. 面试记录表   —— 11 份推荐候选人：面试记录(问题+分组+为什么问+期望+风险) + 问题分组
  3. 招聘进度表   —— 2 岗位：岗位名称/需求人数/当前状态

用法：
    python3 sync_scores.py           # 全量写回三张表（清空旧数据后重写）
    python3 sync_scores.py --dry-run # 只打印，不写飞书
"""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

from matcher_v2 import (FeishuClient, feishu_to_resume, match_job_family,
                        score_feishu_resume, make_summary)
from jd_generator import load_family
from interview_collect import generate_core_questions
from config import (JD_TABLE_ID, RESUME_TABLE_ID, RESULT_TABLE_ID,
                    INTERVIEW_TABLE_ID, PROGRESS_TABLE_ID, WEIGHT_TABLE_ID)

# 新三分类 → 飞书「推荐结论」既有选项的映射
STATUS_TO_CONCLUSION = {
    "推荐": "通过筛选",
    "待确认": "待定",
    "不推荐": "淘汰",
}

# 面试题的期望信号/风险信号（按维度）
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


def _grade_to_field(grade: str) -> str:
    """等级映射到「评分结果表.等级」的既有选项（信息不足无对应选项，留空）。"""
    if grade in ("A级", "B级", "C级", "不推荐"):
        return grade
    return ""


def _dimension_text(score: dict) -> str:
    """把维度明细（含扣分原因）+ 推荐/待确认/淘汰原因 + 风险（含每条等级）拼成可读多行文本。"""
    lines = []
    for d in score.get("dimension_scores", []):
        w = round(d.get("weight", 0) * 100)
        s = d.get("score", 0)
        ev = d.get("evidence", "") or "无"
        state = d.get("state", "")
        ded = d.get("deduction_reason", "")
        seg = f"· {d['dimension_name']}（{w}%）→ {s} 分[{state}] {ev}"
        if ded:
            seg += f"（扣分：{ded}）"
        lines.append(seg)
    reasons = []
    if score.get("recommend_reasons"):
        reasons.append("推荐：" + "；".join(score["recommend_reasons"][:3]))
    if score.get("pending_reasons"):
        reasons.append("待确认：" + "；".join(score["pending_reasons"][:3]))
    if score.get("reject_reasons"):
        reasons.append("淘汰：" + "；".join(score["reject_reasons"][:3]))
    risks = score.get("risk_warnings", [])
    if risks:
        reasons.append("风险：" + "；".join(
            f"{r['risk_type']}[{r.get('risk_level','')}]（{r.get('suggested_verify_question','')}）"
            for r in risks[:3]))
    if reasons:
        lines.append("——")
        lines.extend(reasons)
    return "\n".join(lines)


def _interview_text(resume: dict, family_key: str, score: dict) -> tuple[str, list[str]]:
    """把结构化面试题拼成可读文本（分组/为什么问/期望/风险），返回 (文本, 分组列表)。"""
    questions = generate_core_questions(family_key, resume, score.get("风险点", []))
    lines = []
    groups = []
    for i, q in enumerate(questions, 1):
        group = "硬条件核验" if q["维度"] in ("倒班接受", "到岗时间", "证书核验") else "素质追问"
        if group not in groups:
            groups.append(group)
        expected, risk = QUESTION_SIGNALS.get(q["维度"], ("给出明确回答", "回答含糊"))
        lines.append(f"{i}. [{group}] {q['问题']}")
        lines.append(f"   为什么问：核验{q['维度']}")
        lines.append(f"   期望信号：{expected}")
        lines.append(f"   风险信号：{risk}")
    return "\n".join(lines), groups


# 各维度评分规则（对齐 scoring.py，写进「权重配置表.评分规则」供 HR 查看）
DIMENSION_RULES = {
    "到岗工期": "随时/立即=10，1周=9，2周=8，1个月=8，更晚=3，未填=未知",
    "倒班接受": "接受倒班/站班=10，明确不接受=2，未明确=未知",
    "制造业经验": "对口(装配/制造/家电/生产等)≥5年=10、3-5=9、1-3=7、<1=4，不对口各减1，无明细=未知",
    "稳定性": "最近一段≥5年=10、3-5=9、2-3=8、1.5-2=7、1-1.5=6、0.5-1=4、<0.5=2，无明细=未知",
    "现场适配": "命中5S/精益/安全/质量/定置等关键词，4+每命中×2，上限10，无信号=未知",
    "专业经验": "专业大类对口=10、不对口=3、无法判断=未知",
    "沟通协同": "命中沟通/协作/协同/推动/跨部门/谈判等，5+每命中，上限10，无信号=未知",
    "数据整理": "命中ERP/WMS/Excel/SAP/SQL/BI，5+每命中，上限10，无工具=3",
    "流程意识": "命中5S/精益/价值流/标准化/改善等，4+每命中×2，上限10，无信号=未知",
    "稳定落地": "最近一段≥5年=10、3-5=9、2-3=8、1.5-2=7、1-1.5=6、0.5-1=4、<0.5=2，无明细=未知",
    "软实力": "命中吃苦/倒班/协作/团队/纪律/抗压/认真/责任/踏实，每命中+2，上限10，无评价=未知",
    "经验": "总年限+行业对口分档，对口≥5=10、3-5=9、1-3=7、<1=4，不对口各减1，无经历=未知",
    "技能": "required命中率×8 + preferred命中+1 + 证书+1，上限10，无技能无证书=未知",
    "专业对口": "专业大类对口=10、不对口=3、无法判断=未知",
}


def build_weight_rows():
    """从 job_families_v2.json 读取当前岗位族软条件权重，同步到「权重配置表」。"""
    import json
    base = pathlib.Path(__file__).resolve().parent
    families = json.loads((base / "job_families_v2.json").read_text(encoding="utf-8"))["job_families"]
    rows = []
    for fam in families:
        for dim in fam.get("soft_scores", []):
            rows.append({
                "岗位族": fam["key"],
                "维度": dim["dim"],
                "权重": dim.get("weight", 0),
                "评分规则": DIMENSION_RULES.get(dim["dim"], dim.get("note", "")),
            })
    return rows


def build_all_rows():
    feishu = FeishuClient()
    jd_records = [r for r in feishu.get_records(JD_TABLE_ID) if r["fields"].get("岗位名称")]
    resume_records = [r for r in feishu.get_records(RESUME_TABLE_ID) if r["fields"].get("姓名")]

    score_rows = []
    interview_rows = []
    for r in resume_records:
        fields = r["fields"]
        target_job = fields.get("应聘岗位", "") or ""
        family_key = match_job_family(target_job)
        if family_key is None:
            continue
        family = load_family(family_key)
        resume = feishu_to_resume(fields)
        score = score_feishu_resume(resume, family)

        score_rows.append({
            "候选人": resume["name"],
            "岗位名称": target_job,
            "匹配度": score["match_score"] if score["match_score"] is not None else "",
            "推荐结论": STATUS_TO_CONCLUSION.get(score["screening_status"], "待定"),
            "等级": _grade_to_field(score.get("等级", "")),
            "风险等级": score.get("风险等级", "低"),
            "下一步动作": score.get("next_action", ""),
            "决策摘要": score.get("decision_summary", ""),
            "匹配总结": make_summary(resume, score),
            "多行文本": _dimension_text(score),
        })

        # 推荐候选人 → 生成结构化面试题写进「面试记录表」
        if score["screening_status"] == "推荐":
            text, groups = _interview_text(resume, family_key, score)
            interview_rows.append({
                "候选人姓名": resume["name"],
                "面试阶段": "待面试",
                "面试记录": text,
                "问题分组": "、".join(groups),
                "面试评价": "",
                "面试结果": "",
            })

    score_rows.sort(key=lambda x: (x["岗位名称"], -(x["匹配度"] if isinstance(x["匹配度"], (int, float)) else 0)))

    # 招聘进度：每个岗位一条
    progress_rows = []
    for jd in jd_records:
        job_name = jd["fields"].get("岗位名称", "")
        try:
            headcount = int(jd["fields"].get("需求人数") or 0)
        except (TypeError, ValueError):
            headcount = 0
        progress_rows.append({
            "岗位名称": job_name,
            "需求人数": headcount,
            "已入职人数": 0,
            "当前状态": "招聘中",
        })

    return score_rows, interview_rows, progress_rows


def _write_table(feishu: FeishuClient, table_id: str, rows: list[dict], label: str) -> None:
    cleared = feishu.clear_table(table_id)
    print(f"[{label}] 清空旧数据 {cleared} 条")
    if not rows:
        print(f"[{label}] 无数据可写")
        return
    result = feishu.create_records(table_id, rows)
    code = result.get("code")
    if code == 0:
        print(f"[{label}] ✅ 写回 {len(result.get('data', {}).get('records', []))} 条")
    else:
        print(f"[{label}] ❌ 写回失败: code={code} msg={result.get('msg','')}")


def main():
    dry_run = "--dry-run" in sys.argv
    score_rows, interview_rows, progress_rows = build_all_rows()
    weight_rows = build_weight_rows()

    from collections import Counter
    c = Counter(r["推荐结论"] for r in score_rows)
    print(f"评分结果 {len(score_rows)} 条，推荐结论分布: {dict(c)}")
    print(f"面试记录 {len(interview_rows)} 条（推荐候选人）")
    print(f"招聘进度 {len(progress_rows)} 条（岗位）")
    print(f"权重配置 {len(weight_rows)} 条（6 岗位族软条件）")

    if dry_run:
        print("\n=== 预览 ===")
        for r in score_rows[:3]:
            print(f"  评分: {r['候选人']} | {r['匹配度']}分 | {r['推荐结论']} | 下一步[{r['下一步动作']}]")
            print(f"    决策摘要: {r['决策摘要']}")
        for r in interview_rows[:1]:
            print(f"  面试: {r['候选人姓名']} | 分组[{r['问题分组']}]\n{r['面试记录'][:200]}...")
        for r in weight_rows[:5]:
            print(f"  权重: {r['岗位族']}.{r['维度']} = {r['权重']}")
        print("\n（--dry-run 模式，未写飞书）")
        return

    feishu = FeishuClient()
    _write_table(feishu, RESULT_TABLE_ID, score_rows, "评分结果表")
    _write_table(feishu, INTERVIEW_TABLE_ID, interview_rows, "面试记录表")
    _write_table(feishu, PROGRESS_TABLE_ID, progress_rows, "招聘进度表")
    _write_table(feishu, WEIGHT_TABLE_ID, weight_rows, "权重配置表")
    print("\n✅ 四张表已全部同步到飞书（评分/面试/进度/权重）")


if __name__ == "__main__":
    main()
