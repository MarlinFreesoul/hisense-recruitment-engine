"""
海信 AI 招聘智能体 · 风险识别与资质核验（确定性规则版）
========================================================
对照 require.txt 模块 2 的全部要求：

  · 简历造假   —— 时间线重叠 / 学历与工作矛盾 / 任职时长与时间段不符（确定性信号）
  · 工作经历断层 —— 基于「日期区间」精确计算相邻两段工作 Gap≥3 月 / 毕业到首份工作 Gap
  · 证书过期   —— 区分「实际已过期」（高）与「未注明有效期」（中，待核验）
  · 频繁跳槽   —— 段数≥3 且平均每段<1 年
  · 期望错位   —— 求职意向与目标岗位不一致
  · 核心技能真实性初步核验 —— 技术/职能岗：声称的核心技能是否在履历/证书中有佐证

设计原则（与 scoring 一致）：
  · 简历里判不了的（实操水平、是否真会）一律「标风险 + 给核验动作」，交面试 STAR / 背调，
    机器不代替人工下结论。
  · 每条风险都带 `advice`（给面试官/HR 的核验动作），不是只贴标签。

向后兼容：detect_risks / risk_report 的 family 参数可选，旧调用方不传也能跑。
"""
from __future__ import annotations
import re
from datetime import date
from typing import Any

# 技术 / 职能岗位族（require.txt 点名要做核心技能真实性核验的岗位类型）
TECH_FUNCTIONAL_FAMILIES = {
    "process-equipment",   # 工艺/IE/设备
    "quality",             # 质量/测试/检验
    "rnd-engineering",     # 研发/工程技术
    "procurement-logistics",  # 采购/物流/计划
    "production-management",  # 现场管理/管培
}


# ============== 日期解析 ==============
def _parse_date_token(s: str) -> date | None:
    """从 '2023-07' / '2023-07-15' / '2023.7' 中解析出 date（日缺省为 1 号）。"""
    if not s:
        return None
    m = re.search(r"(\d{4})[-./](\d{1,2})(?:[-./](\d{1,2}))?", s)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3) or 1))
    except ValueError:
        return None


def _parse_period(period: Any) -> tuple[date | None, date | None]:
    """解析 '2023-07 ~ 至今' / '2020-09 ~ 2023-06' / '2020.09至2023.06'。
    返回 (start, end)，end=None 表示「至今/在岗」。
    """
    if not period or not isinstance(period, str):
        return None, None
    low = period.lower()
    # 以 ~ ～ — – 至 或 " - " 作为起止分隔符（避免误拆日期内部的连字符）
    parts = [p.strip() for p in re.split(r"[~～—–]|至| - ", period) if p.strip()]
    if not parts:
        return None, None
    start = _parse_date_token(parts[0])
    end: date | None = None
    if len(parts) >= 2:
        tail = parts[1]
        if any(k in low for k in ("至今", "present", "现在", "current")):
            end = None  # 在岗
        else:
            end = _parse_date_token(tail)
    if start is None and len(parts) == 1 and any(k in low for k in ("至今", "present")):
        # 形如 "至今"，无起点信息
        return None, None
    return start, end


# ============== 履历分段 ==============
def _segments(resume: dict) -> tuple[list[dict], list[dict]]:
    """返回 (全部段, 含日期的可排序段)。无日期的段只保留 tenure 用于短期任职判定。"""
    all_segs, dated = [], []
    for w in resume.get("work_experience", []) or []:
        start, end = _parse_period(w.get("period", ""))
        dur = float(w.get("duration_years", 0) or 0)
        seg = {"start": start, "end": end, "dur": dur, "raw": w}
        all_segs.append(seg)
        if start is not None:
            dated.append(seg)
    dated.sort(key=lambda s: s["start"])
    return all_segs, dated


# ============== 风险识别主函数 ==============
def detect_risks(resume: dict, family: dict | None = None) -> list[dict]:
    risks: list[dict] = []
    work = resume.get("work_experience", []) or []
    edu = resume.get("education", {}) or {}
    certs = resume.get("certificates", []) or []
    expected = resume.get("expected", {}) or {}

    today = date.today()
    all_segs, dated = _segments(resume)

    # ---------- 1. 简历造假（确定性时间线信号） ----------
    # 1a. 相邻工作重叠
    for i in range(1, len(dated)):
        prev, cur = dated[i - 1], dated[i]
        if prev["end"] is None or cur["start"] < prev["end"]:
            risks.append({
                "type": "简历造假", "level": "高",
                "detail": (f"第{i}段（{cur['start']:%Y-%m}~{cur['end']:%Y-%m}）与第{i-1}段"
                           f"（{prev['start']:%Y-%m}~{prev['end']:%Y-%m}）工作时间重叠，疑似时间线造假"),
                "advice": "请核验各段工作经历真实性（社保/合同/背调证明人）",
            })
    # 1b. 首份工作早于毕业（时间线矛盾）
    edu_end = _parse_period(edu.get("period", ""))[1] if edu.get("period") else None
    if edu_end and dated:
        first_start = dated[0]["start"]
        gap_days = (first_start - edu_end).days
        if gap_days < -180:  # 早毕业超过半年开始工作 → 矛盾
            risks.append({
                "type": "简历造假", "level": "高",
                "detail": (f"首份工作开始（{first_start:%Y-%m}）早于毕业（{edu_end:%Y-%m}）"
                           f"约{-gap_days // 30}个月，学历与工作时间为矛盾"),
                "advice": "请核实用人时间与学历真实性（学信网/背调）",
            })
    # 1c. 任职时长与时间段跨度不符（跳过 end=None 的在岗段，无法算跨度）
    for s in dated:
        if s["dur"] and s["start"] and s["end"]:
            span = (s["end"] - s["start"]).days / 365.25
            if abs(span - s["dur"]) > 1.5:
                risks.append({
                    "type": "简历造假", "level": "中",
                    "detail": f"任职时长标注 {s['dur']} 年，与时间段跨度 {span:.1f} 年不符",
                    "advice": "请核验实际任职时长（合同/社保起止）",
                })

    # ---------- 2. 工作经历断层（日期区间 Gap） ----------
    GAP_HIGH = 180  # ≥6 个月判高
    for i in range(1, len(dated)):
        prev_end = dated[i - 1]["end"]
        if prev_end is None:  # 上前一段仍在岗，无法算空窗
            continue
        cur_start = dated[i]["start"]
        gap_days = (cur_start - prev_end).days
        if gap_days >= 90:  # ≥3 个月
            months = gap_days // 30
            level = "高" if gap_days >= GAP_HIGH else "中"
            risks.append({
                "type": "工作经历断层", "level": level,
                "detail": (f"第{i}段工作开始（{cur_start:%Y-%m}）与上前一段结束"
                           f"（{prev_end:%Y-%m}）间隔约 {months} 个月空窗"),
                "advice": "请确认空窗期去向（求学/待业/创业），背调核实",
            })
    # 毕业 → 首份工作断层
    if edu_end and dated:
        first_start = dated[0]["start"]
        gap_days = (first_start - edu_end).days
        if gap_days >= 90:
            months = gap_days // 30
            level = "高" if gap_days >= GAP_HIGH else "中"
            risks.append({
                "type": "工作经历断层", "level": level,
                "detail": (f"毕业（{edu_end:%Y-%m}）到首份工作（{first_start:%Y-%m}）"
                           f"间隔约 {months} 个月空窗"),
                "advice": "请确认毕业后空窗期去向，背调核实",
            })

    # ---------- 3. 短期任职（替代旧「稳定性」弱代理） ----------
    for s in all_segs:
        if s.get("dur") and s["dur"] < 0.5:
            risks.append({
                "type": "短期任职", "level": "中",
                "detail": f"存在一段任职仅 {s['dur']} 年（<6 个月），稳定性存疑",
                "advice": "请确认离职原因与稳定承诺",
            })

    # ---------- 4. 频繁跳槽 ----------
    if len(work) >= 3:
        avg = sum(float(w.get("duration_years", 0) or 0) for w in work) / len(work)
        if avg < 1:
            risks.append({
                "type": "频繁跳槽", "level": "中",
                "detail": f"{len(work)} 段工作，平均每段 {avg:.1f} 年",
                "advice": "请确认离职原因与稳定承诺",
            })

    # ---------- 5. 证书过期 / 证书核验 ----------
    for c in certs:
        name = c.get("name", "")
        expiry = c.get("expiry")
        if not expiry or expiry in ("未注明", "", None):
            risks.append({
                "type": "证书核验", "level": "中",
                "detail": f"证书「{name}」未注明有效期，需核验",
                "advice": "请核验证书原件与有效期",
            })
        else:
            exp_date = _parse_date_token(str(expiry))
            if exp_date is None:
                risks.append({
                    "type": "证书核验", "level": "中",
                    "detail": f"证书「{name}」有效期「{expiry}」无法识别，需核验",
                    "advice": "请核验证书原件与有效期",
                })
            elif exp_date < today:
                risks.append({
                    "type": "证书过期", "level": "高",
                    "detail": f"证书「{name}」已于 {exp_date:%Y-%m-%d} 过期",
                    "advice": "过期证书不予采信，请核验最新有效证书",
                })
            # 有效期在未来 → 有效，不标风险

    # ---------- 6. 期望错位 ----------
    intention = expected.get("career_intention", "")
    target = expected.get("target_position", "")
    if intention and target and intention not in target:
        risks.append({
            "type": "期望错位", "level": "中",
            "detail": f"求职意向「{intention}」与目标岗位「{target}」存在落差，留存风险",
            "advice": "请电话确认求职意向与留存意愿",
        })

    # ---------- 7. 核心技能真实性初步核验（技术/职能岗） ----------
    risks += _skill_authenticity(resume, family)

    if not risks:
        risks.append({"type": "无", "level": "低", "detail": "简历层面未发现可判风险点", "advice": ""})

    return risks


def _skill_authenticity(resume: dict, family: dict | None) -> list[dict]:
    """技术/职能岗：声称的核心技能（skill_model.required + 研发族领域词库 sub_disciplines）
    若仅出现在技能清单、而在工作履历/证书中无任何佐证，则标「真实性待核验」——
    机器不判真假，只提示面试/背调核验。

    制造业垂直知识库（冰箱研发细分领域词）在此被真正用于「技能真实性核验」：
    候选人技能清单里点到的制冷/结构/风道电控等领域词，若履历无佐证，逐一提示 STAR 核验。
    """
    if not family:
        return []
    if family.get("key") and family["key"] not in TECH_FUNCTIONAL_FAMILIES:
        # 一线生产岗以硬条件/体力为主，不做核心技能真实性核验（避免噪声）
        return []
    sm = family.get("skill_model") or {}
    required = list(sm.get("required", []) or [])
    # 研发族：把领域词库（sub_disciplines.keywords）纳入核验池，但仅针对候选人「技能清单里点到」的词，
    # 避免对非研发岗/未主张领域产生噪声。
    if family.get("key") == "rnd-engineering":
        for sd in (family.get("sub_disciplines") or []):
            for kw in sd.get("keywords", []) or []:
                if kw not in required:
                    required.append(kw)
    if not required:
        return []

    claimed = set(resume.get("skills", []) or [])
    # 佐证语料：仅取「履历（职责/业绩）+ 证书名」，不含技能清单本身，
    # 这样才能区分「自称」与「有证据支撑」。
    evidence_parts = []
    for w in resume.get("work_experience", []) or []:
        evidence_parts += list(w.get("duties", []) or [])
        evidence_parts += list(w.get("achievements", []) or [])
    for c in resume.get("certificates", []) or []:
        evidence_parts.append(str(c.get("name", "")))
    evidence = " ".join(evidence_parts).lower()

    out = []
    for skill in required:
        # 仅核验候选人技能清单里「主张」过的领域词，避免对非主张词产生噪声
        if skill in claimed and skill.lower() not in evidence:
            out.append({
                "type": "核心技能真实性待核验", "level": "中",
                "detail": (f"核心技术「{skill}」仅出现在技能清单，工作履历/证书中无佐证，"
                           f"真实性待核验"),
                "advice": f"面试实操或背调核验「{skill}」真实水平",
            })
    return out


def risk_report(resume: dict, family: dict | None = None) -> dict:
    risks = detect_risks(resume, family)
    levels = {"低": 1, "中": 2, "高": 3}
    overall = max((levels.get(r["level"], 1) for r in risks), default=1)
    return {
        "risks": risks,
        "overall_level": {1: "低", 2: "中", 3: "高"}[overall],
        "deferred_to": [
            "面试 STAR 追问（造假/技能真实性实操核验）",
            "背调（证书/犯罪/断层/任职时长核实）",
            "体检（健康）",
        ],
    }


if __name__ == "__main__":
    import json, pathlib
    base = pathlib.Path(__file__).resolve().parent.parent
    resume = json.loads((base / "sample_resume.json").read_text(encoding="utf-8"))
    print(json.dumps(risk_report(resume), ensure_ascii=False, indent=2))
