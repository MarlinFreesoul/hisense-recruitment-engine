"""
海信 AI 招聘智能体 · 简历解析器
==============================
文本优先 PyMuPDF（pdf 抽取），扫描件 OCR 兜底（此处留接口）。
结构化：先用确定性规则抽取清晰字段，复杂字段留 LLM 抽取点（llm_extract）。

输出的 resume JSON 与 JD 字段同构，是 screening/risk 的输入。
"""
from __future__ import annotations
import re
from typing import Any


def extract_text_from_pdf(pdf_path: str) -> str:
    """文本优先 PyMuPDF；失败则返回空，交由 OCR 兜底。"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text
    except Exception as e:
        print(f"[resume_parser] PDF 文本抽取失败（{e}），需 OCR 兜底")
        return ""


def _pick(pattern: str, text: str, default: Any = None) -> Any:
    m = re.search(pattern, text)
    if not m:
        return default
    try:
        return m.group(1).strip()
    except IndexError:
        return m.group(0).strip()


def parse_resume(text: str) -> dict:
    """规则版结构化：从简历文本抽取关键字段，产出与 JD 同构的 resume JSON。"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # 求职岗位（通常前几行）
    target = next((l for l in lines[:8] if "岗位" in l or "求职" in l or "目标" in l), "")
    target = _pick(r"[:：]\s*(.+)", target, default="") or target

    # 年龄范围
    age = _pick(r"(\d{2}\s*[-~]\s*\d{2}\s*岁|\d{2}\s*岁)", text, default="")

    # 学历
    degree = ""
    for d in ["博士", "硕士", "本科", "大专", "中专", "中技", "高中", "初中"]:
        if d in text:
            degree = d
            break

    # 专业
    major = _pick(r"机械制造|机械设计|电气|自动化|制冷|材料|电子|工业工程|物流|供应链|质量|安全工程|化学", text, default="")

    # 技能：从「专业技能/技能」区块抓
    skill_block = _pick(r"专业技能\s*\n(.+?)(?=\n\s*\n|\n证书|\n期望)", text, default="")
    skills = [s.strip() for s in re.split(r"[\s、,，]+", skill_block) if s.strip()][:20]

    # 证书
    cert_block = _pick(r"证书[资质]*\s*\n(.+?)(?=\n\s*\n|\n期望|\n技能)", text, default="")
    certs = [{"name": c.strip(), "expiry": "未注明"} for c in re.split(r"[、,，\s]+", cert_block) if c.strip()]

    # 自我评价
    self_eval = _pick(r"自我评价\s*\n(.+)", text, default="") or text[-200:]

    # 到岗时间
    avail = _pick(r"(?:到岗时间|到岗)[:：]?\s*(.+)", text, default="")

    # 求职意向
    intention = _pick(r"求职意向[:：]?\s*(.+)", text, default="")

    return {
        "name": _pick(r"候选人[A-Z]|[一-龥]{2,4}(?=\s*$)", lines[0] if lines else "", default="候选人"),
        "age_range": age,
        "education": {"degree": degree, "major": major, "school": _pick(r"(\S+学院|\S+大学)", text, default="")},
        "work_experience": _parse_work(text),
        "skills": skills,
        "certificates": certs,
        "self_evaluation": self_eval.strip(),
        "expected": {
            "target_position": target,
            "available_date": avail,
            "career_intention": intention,
        },
    }


def _parse_work(text: str) -> list[dict]:
    """粗规则抽取工作经历（MVP：抓「公司·职位·时间」）。复杂版走 llm_extract。"""
    works = []
    # 匹配 时间区间
    periods = re.findall(r"(\d{4}[.\-/]\d{1,2})\s*[-~—至]\s*(至今|现在|\d{4}[.\-/]\d{1,2})", text)
    positions = re.findall(r"(?:·|：|:)\s*(装配工|工艺工程师|质量|设备|采购|普工|包装|生产|研发|工程师|操作工)", text)
    for i, (start, end) in enumerate(periods[:5]):
        pos = positions[i] if i < len(positions) else "未识别"
        years = _duration_years(start, end)
        works.append({
            "position": pos, "period": f"{start}~{end}",
            "duration_years": years, "company": "未识别",
            "duties": [], "achievements": [],
        })
    return works


def _duration_years(start: str, end: str) -> float:
    try:
        sy = int(start[:4]); sm = int(start[5:7].strip(".-/") or 6)
        if end in ("至今", "现在"):
            ey, em = 2026, 8  # 当前时间基准
        else:
            ey = int(end[:4]); em = int(end[5:7].strip(".-/") or 6)
        return round((ey - sy) + (em - sm) / 12, 1)
    except Exception:
        return 0.0


def llm_extract(text: str, schema: str) -> dict:
    """LLM 抽取点：规则版抽不出的复杂字段，在此接入 LLM（保留接口，MVP 暂用规则兜底）。"""
    raise NotImplementedError("LLM 抽取点：接入 LLM 后替换此处（如教育经历级联、项目证据链）")


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if path:
        txt = extract_text_from_pdf(path)
        print(parse_resume(txt) if txt else "OCR 兜底未实现，文本抽取为空")
