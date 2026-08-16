"""
AI 招聘智能体 · 整合评分系统（matcher_v2 · 完整版）
==================================================
= 飞书读写 + 岗位族知识库 + 确定性评分 + 风险识别 + 写回评分结果表

数据流：
  飞书 JD（招聘需求表）─岗位名匹配─> 岗位族（job_families_v2.json 模板+权重）
  飞书简历（简历库）  ─字段映射──> resume 结构
  二者 ─确定性评分+风险─> 匹配度 + 风险 + 报告 → 写回「评分结果表」

非标简历容错：字段缺失不崩溃，降级标注 _missing_fields。
"""
from __future__ import annotations
import json
import time
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from scoring import (score_stability, score_soft_qualities, score_experience,
                     score_skills, score_major_match, score_arrival, score_shift,
                     score_data_tools, score_process, score_communication,
                     score_education, UNKNOWN, SATISFIED, UNSATISFIED)
from jd_generator import load_family
from risk_filter import risk_report
from interview import generate_questions, format_questions_text
from talent import write_progress

# ============== 飞书配置（凭证从 config.py / .env 读，不硬编码） ==============
from config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_BASE_TOKEN, \
    JD_TABLE_ID, RESUME_TABLE_ID, RESULT_TABLE_ID, WEIGHT_TABLE_ID, \
    INTERVIEW_TABLE_ID, PROGRESS_TABLE_ID

BASE_APP_TOKEN = FEISHU_BASE_TOKEN


# ============== 飞书客户端 ==============
class FeishuClient:
    def __init__(self):
        self.token = None
        self.token_expires_at = 0

    def get_token(self) -> str:
        if self.token and time.time() < self.token_expires_at - 60:
            return self.token
        import requests
        r = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                          json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}, timeout=30).json()
        if r.get("code") == 0:
            self.token = r["tenant_access_token"]
            self.token_expires_at = time.time() + r.get("expire", 7200)
            return self.token
        raise Exception(f"获取 token 失败: {r}")

    def _hdr(self):
        return {"Authorization": f"Bearer {self.get_token()}", "Content-Type": "application/json"}

    def get_records(self, table_id: str) -> list[dict]:
        import requests
        records, pt = [], None
        while True:
            params = {"page_size": 100}
            if pt:
                params["page_token"] = pt
            r = requests.get(f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_APP_TOKEN}/tables/{table_id}/records",
                             headers=self._hdr(), params=params, timeout=30).json()
            if r.get("code") == 0:
                records += r["data"]["items"] or []
                if r["data"].get("has_more"):
                    pt = r["data"]["page_token"]
                else:
                    break
            else:
                raise Exception(f"读记录失败: {r}")
        return records

    def create_records(self, table_id: str, fields_list: list[dict]) -> dict:
        import requests
        r = requests.post(f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_APP_TOKEN}/tables/{table_id}/records/batch_create",
                          headers=self._hdr(),
                          json={"records": [{"fields": f} for f in fields_list]}, timeout=30).json()
        return r

    def clear_table(self, table_id: str) -> int:
        """清空一张表的所有记录，返回删除条数。"""
        import requests
        ids = [r["record_id"] for r in self.get_records(table_id)]
        if not ids:
            return 0
        r = requests.post(f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_APP_TOKEN}/tables/{table_id}/records/batch_delete",
                          headers=self._hdr(), json={"records": ids}, timeout=30).json()
        if r.get("code") != 0:
            raise Exception(f"清空失败: {r}")
        return len(ids)


# ============== 岗位族匹配 ==============
FAMILY_KEYWORDS = {
    "firstline": ["装配", "包装", "普工", "小时工", "临时工", "操作工", "钣金", "发泡", "钎焊", "生产员", "打螺丝", "贴标"],
    "production-management": ["管培", "班组长", "领班", "生产管理", "储备干部", "线长", "车间主任"],
    "process-equipment": ["工艺", "设备", "IE", "模具", "维修", "精益"],
    "quality": ["质量", "质检", "品保", "检验", "测试", "品质", "品控", "安全", "EHS", "消防", "环保"],
    "procurement-logistics": ["采购", "物流", "仓储", "计划", "供应链", "资材"],
    "rnd-engineering": ["嵌入式", "研发", "软件", "算法", "开发", "数据库"],
}


# ============== 淘汰信号分级（对齐陈老师标准） ==============
# 一票否决信号：求职意向错位（留存风险，直接不推荐，分再高也救不回）
REJECT_SIGNAL_KEYWORDS = ["意向不符", "意向偏离", "意向偏低", "意向偏高"]

# 重淘汰信号：明显不匹配 / 硬伤 / 诚信风险 → 每个扣 15 分（可累计）
# 轻信号（到岗2周/薪资略高/通勤/需确认/单项能力缺失）不在此列，落入待确认交给电话确认
HEAVY_SIGNAL_KEYWORDS = [
    # 倒班硬伤（一线生产核心硬条件）
    "不接受倒班", "不接受站班", "不接受加班",
    # 稳定性硬伤
    "频繁跳槽", "断层",
    # 诚信风险（数据造假嫌疑）
    "数据夸张", "数据不合理",
    # 薪资严重错位（远超/超岗位/超上限，非「略高」）
    # 注意：飞书写成「薪资期望超岗位上限」，中间隔着「期望」，故匹配「超」字部分而非「薪资」前缀
    "远超", "超岗位", "超上限",
    # 无制造业经验（只有电商/快递仓）
    "只有电商仓", "只有快递仓", "只有电商", "只有快递", "缺少制造业", "无制造业",
    # 经验严重缺失
    "应届无项目", "只有实习",
    # 简历质量
    "信息过于简单",
    # 到岗明确不满足（太晚）
    "到岗时间不满足", "到岗不满足",
    # 明显不对口
    "偏IT",
]


def classify_risk_signals(risk_signals: list[str]) -> tuple[bool, int]:
    """把风险信号分成 (是否一票否决, 重信号累计扣分)。轻信号不计入。"""
    reject = any(any(k in sig for k in REJECT_SIGNAL_KEYWORDS) for sig in risk_signals)
    penalty = 15 * sum(1 for sig in risk_signals if any(k in sig for k in HEAVY_SIGNAL_KEYWORDS))
    return reject, penalty


def match_job_family(job_name: str):
    """返回岗位族 key，匹配不上返回 None（未识别，不硬归一线岗）。"""
    for key, kws in FAMILY_KEYWORDS.items():
        if any(k in job_name for k in kws):
            return key
    return None


# ============== 飞书权重配置 ==============
def load_weights_from_feishu(feishu) -> dict:
    """从飞书「权重配置表」读权重，返回 {岗位族key: {维度: weight}}。HR 在飞书改权重实时生效。"""
    weights = {}
    for r in feishu.get_records(WEIGHT_TABLE_ID):
        f = r["fields"]
        family_key = f.get("岗位族", "")
        dim = f.get("维度", "")
        w = f.get("权重", 0)
        if family_key and dim:
            try:
                weights.setdefault(family_key, {})[dim] = float(w)
            except (TypeError, ValueError):
                pass
    return weights


def apply_feishu_weights(family: dict, weights: dict) -> dict:
    """用飞书权重覆盖 family 的 soft_scores 权重（不改动 JSON 原文件）。"""
    if not weights:
        return family
    for dim in family.get("soft_scores", []):
        if dim["dim"] in weights:
            dim["weight"] = weights[dim["dim"]]
    return family


# ============== 字段映射 ==============
def feishu_to_resume(fields: dict) -> dict:
    certs_text = fields.get("证书", "") or ""
    certs = [{"name": c.strip(), "expiry": "未注明"} for c in re.split(r"[、,，;；\s]+", certs_text) if c.strip()]
    return {
        "name": fields.get("姓名", "") or "",
        "age_range": fields.get("年龄", "") or "",
        "education": {
            "degree": fields.get("最高学历", "") or "",
            "school": fields.get("毕业院校", "") or "",
            "major": fields.get("专业", "") or "",
        },
        "work_experience": [{
            "company": fields.get("最近公司", "") or "",
            "position": fields.get("最近职位", "") or "",
            "duration_years": float(fields.get("工作年限", 0) or 0),
            "duties": [fields.get("工作经历简述", "") or ""],
        }],
        "skills": fields.get("核心技能", []) or [],
        "certificates": certs,
        "self_evaluation": (fields.get("自我评价", "") or fields.get("工作经历简述", "") or ""),
        "expected": {"available_date": fields.get("期望到岗", "") or ""},
        "risk_signals": (fields.get("风险信号", "") or "").split("、") if fields.get("风险信号") else [],
        "_missing_fields": _missing(fields),
    }


def _missing(fields: dict) -> list[str]:
    missing = []
    for k in ["专业", "证书", "自我评价", "期望到岗", "年龄", "核心技能"]:
        if not fields.get(k):
            missing.append(k)
    return missing


# ============== 评分 + 风险 ==============
def _screening_status(score):
    """对齐陈老师推荐等级：90-100立即约面 / 80-89电话确认 / 75-79备选 / 45-74待确认 / 0-44不推荐。

    三分类映射（对齐 10% 推荐 / 30% 待确认 / 60% 不推荐）：
      推荐 = 90-100 + 80-89（明确推荐，约面）
      待确认 = 75-79（备选）+ 45-74（待确认）
      不推荐 = 0-44
    一票否决（意向不符/不接受倒班）已在上游扣分处理，不在此处用学历硬门槛。
    """
    if score is None:
        return "待确认", "电话确认"
    if score >= 90:
        return "推荐", "立即约面"
    if score >= 80:
        return "推荐", "电话确认后约面"
    if score >= 75:
        return "待确认", "加入备选"
    if score >= 45:
        return "待确认", "电话确认"
    return "不推荐", "暂不推进"
RISK_VERIFY_QUESTIONS = {
    "证书核验": "请核验证书原件与有效期",
    "期望错位": "请电话确认求职意向与留存意愿",
    "频繁跳槽": "请确认离职原因与稳定承诺",
    "稳定性": "请确认离职原因与稳定承诺",
}


def score_feishu_resume(resume: dict, family: dict) -> dict:
    dimension_scores = []
    recommend_reasons = []
    pending_reasons = []
    reject_reasons = []
    weighted_sum = 0.0
    applied_weight = 0.0
    for dim in family.get("soft_scores", []):
        key, w = dim["dim"], dim.get("weight", 0.0)
        fn = {"稳定性": score_stability, "软实力": score_soft_qualities,
              "经验": score_experience, "技能": score_skills,
              "专业对口": score_major_match, "学历": score_education,
              "到岗工期": score_arrival, "倒班接受": score_shift,
              "制造业经验": score_experience, "现场适配": score_process,
              "专业经验": score_major_match, "沟通协同": score_communication,
              "数据整理": score_data_tools, "流程意识": score_process,
              "稳定落地": score_stability}.get(key)
        if fn is None:
            dimension_scores.append({"dimension_name": key, "weight": w, "state": "未配置",
                                     "score": 0, "evidence": "", "deduction_reason": ""})
            continue
        state, raw, evidence = fn(resume, family)
        if state == UNKNOWN:
            dimension_scores.append({"dimension_name": key, "weight": w, "state": "未知",
                                     "score": raw, "evidence": evidence, "deduction_reason": ""})
            pending_reasons.append(f"{key}：{evidence}")
            weighted_sum += raw * w
            applied_weight += w
            continue
        weighted_sum += raw * w
        applied_weight += w
        deduction = "" if state == SATISFIED else f"{key}未达标"
        dimension_scores.append({"dimension_name": key, "weight": w, "state": state,
                                 "score": raw, "evidence": evidence, "deduction_reason": deduction})
        if state == SATISFIED:
            recommend_reasons.append(evidence)
        else:
            reject_reasons.append(f"{key}：{evidence}")

    total_weight = sum(d.get("weight", 0) for d in family.get("soft_scores", []))
    score_100 = round(weighted_sum / applied_weight * 10, 1) if applied_weight > 0 else None

    # 淘汰信号分级：意向错位→一票否决；重信号→扣15分；轻信号不罚（落入待确认）
    reject, penalty = classify_risk_signals(resume.get("risk_signals", []))
    if score_100 is not None:
        score_100 = max(0.0, score_100 - penalty)
        if reject:
            score_100 = min(score_100, 44.0)  # 意向错位直接不推荐
    coverage = round(applied_weight / total_weight, 2) if total_weight > 0 else 0.0

    risk = risk_report(resume)
    risk_warnings = [
        {"risk_type": r["type"], "risk_level": r["level"], "evidence": r["detail"],
         "suggested_verify_question": RISK_VERIFY_QUESTIONS.get(r["type"], "请人工核验")}
        for r in risk["risks"] if r["level"] != "低"
    ]

    status, next_action = _screening_status(score_100)
    # 求职意向错位（一票否决）→ 写进淘汰原因
    if reject:
        reject_reasons.insert(0, "求职意向与岗位不符")
    # 不推荐但无具体淘汰原因（维度全未知）→ 补一个明确原因
    if status == "不推荐" and not reject_reasons:
        reject_reasons.append("简历信息严重缺失，无法评估")
    # 决策摘要按状态取对应原因：推荐→推荐原因，待确认→待确认原因，不推荐→淘汰原因
    if status == "推荐":
        summary_reasons = recommend_reasons
    elif status == "待确认":
        summary_reasons = pending_reasons
    else:
        summary_reasons = reject_reasons
    decision_summary = f"{status}：" + ("、".join(summary_reasons[:2]) if summary_reasons else "信息不足")

    return {
        # 陈老师标杆结构
        "match_score": score_100,
        "screening_status": status,
        "next_action": next_action,
        "decision_summary": decision_summary,
        "recommend_reasons": recommend_reasons,
        "pending_reasons": pending_reasons,
        "reject_reasons": reject_reasons,
        "dimension_scores": dimension_scores,
        "risk_warnings": risk_warnings,
        # 兼容旧字段
        "硬性通过": not reject,  # 真硬条件：无求职意向错位即通过（学历已改软打分）
        "软条件明细": dimension_scores,
        "匹配度": score_100,
        "等级": _grade(score_100),
        "信息覆盖度": coverage,
        "风险等级": risk["overall_level"],
        "风险点": [r for r in risk["risks"] if r["level"] != "低"],
        "字段缺口": resume.get("_missing_fields", []),
    }


def _grade(score) -> str:
    """匹配度分级（对照 PRD 学术标准）：81-100 完全匹配 A级 / 61-80 基本匹配 B级 /
    21-60 相当匹配或不匹配 C级 / <21 非常不匹配 不推荐。"""
    if score is None: return "信息不足"
    if score >= 81: return "A级"
    if score >= 61: return "B级"
    if score >= 21: return "C级"
    return "不推荐"


def make_summary(resume: dict, s: dict) -> str:
    degree = resume["education"]["degree"] or "学历未知"
    years = resume["work_experience"][0]["duration_years"] if resume["work_experience"] else 0
    skills = "、".join(resume["skills"][:3]) if resume["skills"] else "无"
    parts = [f"学历{degree}", f"{years:.0f}年经验", f"技能[{skills}]"]
    if resume["education"]["major"]:
        parts.append(f"专业{resume['education']['major']}")
    if s["风险点"]:
        parts.append("风险:" + "、".join(r["type"] for r in s["风险点"][:2]))
    return "，".join(parts)


# ============== 主流程 ==============
def run_matching(top_n: int = 5, write_back: bool = True) -> dict:
    feishu = FeishuClient()
    feishu_weights = load_weights_from_feishu(feishu)  # 读飞书权重配置
    print("[1/4] 读招聘需求...")
    jd_records = [r for r in feishu.get_records(JD_TABLE_ID) if r["fields"].get("岗位名称")]
    print(f"    找到 {len(jd_records)} 个岗位")

    print("[2/4] 读简历库...")
    resume_records = [r for r in feishu.get_records(RESUME_TABLE_ID) if r["fields"].get("姓名")]
    print(f"    找到 {len(resume_records)} 份简历")

    results, write_rows = [], []
    for jd in jd_records:
        job_name = jd["fields"].get("岗位名称", "未知")
        family_key = match_job_family(job_name)
        if family_key is None:
            print(f"[3/4] ⚠️ 岗位「{job_name}」→ 未识别（不在已知 6 大岗位族）")
            results.append({"岗位名称": job_name, "岗位族": "未识别", "候选人数": 0, "TOP": []})
            continue
        family = load_family(family_key)
        family = apply_feishu_weights(family, feishu_weights.get(family_key, {}))  # 应用飞书权重
        print(f"[3/4] 岗位「{job_name}」→ 岗位族「{family['name']}」")

        scored = []
        for r in resume_records:
            resume = feishu_to_resume(r["fields"])
            s = score_feishu_resume(resume, family)
            s["候选人"] = resume["name"]
            s["岗位"] = job_name
            s["匹配总结"] = make_summary(resume, s)
            scored.append(s)
        scored.sort(key=lambda x: x["匹配度"], reverse=True)

        results.append({"岗位名称": job_name, "岗位族": family["name"], "family_key": family_key,
                        "候选人数": len(scored), "TOP": scored[:top_n]})

        if write_back:
            for c in scored[:top_n]:
                write_rows.append({
                    "候选人": c["候选人"], "岗位名称": job_name,
                    "匹配度": c["匹配度"], "等级": c["等级"],
                    "风险等级": c["风险等级"], "匹配总结": c["匹配总结"],
                    "推荐结论": "通过筛选" if c["等级"] in ("A级", "B级") else "待定",
                })

    if write_back and write_rows:
        cleared = feishu.clear_table(RESULT_TABLE_ID)
        print(f"[4/4] 清空旧评分 {cleared} 条，写回 {len(write_rows)} 条...")
        r = feishu.create_records(RESULT_TABLE_ID, write_rows)
        print(f"    写回结果: code={r.get('code')} {r.get('msg', '')}")

    if write_back:
        # 下游：面试题 + 招聘进度
        interview_rows, progress_rows = [], []
        for jr in results:
            if jr["岗位族"] == "未识别":
                continue
            progress_rows.append({"岗位名称": jr["岗位名称"], "需求人数": 0, "当前状态": "招聘中"})
            for c in jr["TOP"]:
                if c["等级"] in ("A级", "B级"):
                    qs = generate_questions(jr["family_key"], None, c.get("风险点", []))
                    interview_rows.append({"候选人姓名": c["候选人"], "面试阶段": "待面试",
                                           "面试记录": format_questions_text(qs)})
        if interview_rows:
            ir = feishu.create_records(INTERVIEW_TABLE_ID, interview_rows)
            print(f"    面试记录写回 {len(interview_rows)} 条: code={ir.get('code')}")
        if progress_rows:
            pr = feishu.create_records(PROGRESS_TABLE_ID, progress_rows)
            print(f"    招聘进度写回 {len(progress_rows)} 条: code={pr.get('code')}")

    return {"success": True, "匹配时间": time.strftime("%Y-%m-%d %H:%M:%S"), "结果": results}


def report_text(data: dict) -> str:
    lines = ["=" * 60, "📋 AI 招聘智能体 · 评分报告", "=" * 60, f"时间: {data.get('匹配时间', '')}", ""]
    for job in data.get("结果", []):
        lines += ["-" * 60, f"🏢 岗位: {job['岗位名称']}（{job['岗位族']}）", f"📊 候选人数: {job['候选人数']}", "", "【TOP】", ""]
        for c in job.get("TOP", []):
            cov = c.get("信息覆盖度", 0)
            lines.append(f"  {c['候选人']} → {c['匹配度']}分 · {c['等级']} · 风险{c['风险等级']} · 覆盖度{cov}")
            lines.append(f"      {c['匹配总结']}")
            states = " | ".join(f"{d['dim']}{d.get('state','')[:2]}" for d in c.get('软条件明细', [])[:5])
            if states:
                lines.append(f"      维度: {states}")
            if cov < 0.6:
                lines.append(f"      ⚠️ 信息覆盖不足({cov})，建议人工补采")
            lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    try:
        data = run_matching(top_n=5)
        print("\n" + report_text(data))
    except Exception as e:
        print(f"\n❌ 错误: {e}")
