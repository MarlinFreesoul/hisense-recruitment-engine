"""JD 深度结构化(规则 + DeepSeek LLM)

把 131 条岗位(16 前程无忧 + 115 BOSS)每条完整结构化:
- 薪资拆 min/max/period/months
- 工作职责 → responsibilities[] 逐条
- 任职资格 → qualifications{education, major[], experience_years, certificates[], hard_skills[], soft_skills[]}
- 硬条件 hard[] / 软条件 soft[](供 screening 消费)

用法:python3 src/jd_structurer.py [--limit N]   # --limit 只结构化前 N 条(测试用)
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from llm import chat_json

_EDU_LEVELS = ["博士", "硕士", "本科", "大专", "中专", "高中", "初中"]


def norm_edu(s: str) -> str:
    if "中技" in s or "中专" in s:
        return "中专"
    for lv in _EDU_LEVELS:
        if lv in s:
            return lv
    return "不限"


def norm_exp(s: str) -> str:
    if not s or s == "未识别":
        return "不限"
    if "应届" in s or "在校" in s:
        return "应届"
    m = re.search(r"\d+", s)
    return f"{m.group(0)}年" if m else "不限"


# 网站 footer 垃圾关键词(用于过滤被污染的字段)
_FOOTER_KW = ["友情链接", "网站地图", "版权所有", "客服热线", "ICP", "意见反馈",
              "沪公网安备", "51job", "前程无忧", "隐私", "用户协议", "登录政策",
              "公司信息", "银行柜员", "我已阅读", "【", "】", "容港路"]


def _split_list(s: str) -> list[str]:
    """拆顿号/逗号列表,整段 footer 垃圾则返回空,并过滤单字符碎片。"""
    if not s:
        return []
    if any(k in s for k in _FOOTER_KW):
        return []
    return [b.strip() for b in s.replace("、", ",").split(",") if b.strip() and len(b.strip()) >= 2]


def parse_salary(raw: str) -> dict:
    """薪资归一化:"2.5-3.5万·13薪" → {min:25000, max:35000, period:"月", months:13}"""
    if not raw:
        return {"min": None, "max": None, "period": "月", "months": 12}
    raw = raw.strip()

    months = 12
    m = re.search(r"(\d{2})\s*薪", raw)
    if m:
        months = int(m.group(1))
        raw = raw.replace(m.group(0), "")

    period = "月"
    if "天" in raw or "/日" in raw:
        period = "天"
    elif "小时" in raw or "/时" in raw:
        period = "小时"

    mult = 1
    if "万" in raw:
        mult = 10000
    elif "K" in raw.upper() or "k" in raw:
        mult = 1000

    nums = re.findall(r"\d+(?:\.\d+)?", raw)
    if not nums:
        return {"min": None, "max": None, "period": period, "months": months}
    vals = [float(n) * mult for n in nums]
    return {"min": int(min(vals)), "max": int(max(vals)), "period": period, "months": months}


# ---- LLM prompts ----

_SYSTEM_51JOB = """你是招聘 JD 结构化助手。把岗位的「工作职责」和「任职资格」拆解成结构化 JSON。

要求:
1. 只输出 JSON,不要任何其他文字。
2. responsibilities:工作职责按编号拆成逐条字符串数组。如果内容其实是网站 footer 垃圾(含"友情链接""网站地图""版权所有""客服热线""ICP""意见反馈""沪公网安备"等字样),返回空数组 []。
3. qualifications 拆解为:
   - education: 学历(本科/大专/硕士/博士等,空则 "")
   - major: 专业要求字符串数组
   - experience_years: 经验最低年数(数字,无则 null)
   - certificates: 证书数组(如 ISO9001、电工证、英语四级)
   - hard_skills: 硬技能数组(有专业门槛、需学习/考证才能掌握的能力,如 PLC、AutoCAD、C语言、焊工、电工证)。不要把"打螺丝、贴标签、打包装、装配、组装、碰焊、冲压"这类流水线动作放进 hard_skills,这些属于 responsibilities。
   - soft_skills: 软实力数组(如 沟通、协调、抗压)

严格按此结构输出 json:
{"responsibilities": ["..."], "qualifications": {"education": "", "major": [], "experience_years": null, "certificates": [], "hard_skills": [], "soft_skills": []}}"""

_SYSTEM_BOSS = """你是招聘 JD 结构化助手。输入是 OCR 识别有错字的中文岗位文本,需要先纠错再结构化。

要求:
1. 只输出 JSON。
2. title: 纠正 OCR 错字后的岗位标题(如"沣塑"→"注塑"、"测员"→"测试员"、"卫包装"→"组装包装"、"现场检鱼"→"现场检验")。
3. responsibilities: 从正文提取的工作职责逐条(在乱码中识别语义,能识别几条算几条,识别不出返回空数组)。
4. qualifications: education/major/experience_years/certificates/hard_skills/soft_skills。其中 hard_skills 只放有专业门槛的技能(PLC、焊工、电工、AutoCAD、C语言),不要把"打螺丝、贴标签、打包装、装配、组装、碰焊、冲压"这类流水线动作放进 hard_skills,这些属于 responsibilities。

严格按此结构输出 json:
{"title": "...", "responsibilities": ["..."], "qualifications": {"education": "", "major": [], "experience_years": null, "certificates": [], "hard_skills": [], "soft_skills": []}}"""


def _extract_boss_bodies(md_path: str) -> dict:
    """从 structured.md 的「逐条OCR正文」里,按 image_XXX 抽取 OCR 正文。"""
    text = Path(md_path).read_text(encoding="utf-8")
    bodies = {}
    for sec in re.split(r"(?=### \d+\.)", text):
        m_img = re.search(r"（(image_\d+)）", sec)
        m_body = re.search(r"```text\n(.*?)```", sec, re.S)
        if m_img and m_body:
            bodies[m_img.group(1)] = m_body.group(1).strip()
    return bodies


def raw_51job(path: str) -> list[dict]:
    items = []
    for i, row in enumerate(csv.DictReader(open(path, encoding="utf-8-sig")), 1):
        items.append({
            "idx": i,
            "source": "51job",
            "title": row["职位名称"].strip(),
            "company": row["公司名称"].strip(),
            "location": row["工作地点"].strip(),
            "salary": row["薪资"],
            "job_type": row["职能类别"].strip(),
            "benefits": _split_list(row["福利"]),
            "keywords": _split_list(row["关键字"]),
            "edu": norm_edu(row["学历要求"]),
            "exp": norm_exp(row["经验要求"]),
            "responsibility": row["工作职责"],
            "qualification": row["任职资格"],
        })
    return items


def raw_boss(md_path: str) -> list[dict]:
    bodies = _extract_boss_bodies(md_path)
    items = []
    for line in Path(md_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 8 or not cells[0].isdigit():
            continue
        seq, img, title, jtype, salary, loc, exp, edu = cells[:8]
        items.append({
            "idx": int(seq),
            "source": "boss",
            "title": title,
            "location": loc,
            "salary": salary,
            "job_type": jtype,
            "edu": norm_edu(edu),
            "exp": norm_exp(exp),
            "ocr": bodies.get(img, ""),
        })
    return items


# 流水线动作/工作内容词,不应出现在 hard[技能] 里
_TASK_WORDS = [
    "打螺丝", "打丝", "贴标签", "贴海绵", "贴铭", "打包装", "打包", "挂件",
    "装配", "组装", "包装", "碰焊", "冲压", "注塑", "放说明书", "看外观",
    "流水线", "电子元件", "撕胶", "装层架", "固定显示器", "装门",
]


def _clean_skill(hard: list, responsibilities: list) -> tuple[list, list]:
    """把 hard[技能] 里误归的工作内容词移到 responsibilities,保证结构统一。"""
    cleaned = []
    resp = list(responsibilities)
    for h in hard:
        if h["field"] == "技能" and any(w in h["requirement"] for w in _TASK_WORDS):
            if h["requirement"] not in resp:
                resp.append(h["requirement"])
            continue
        cleaned.append(h)
    return cleaned, resp


def _build_hard(edu: str, exp: str, quals: dict) -> list:
    hard = []
    if edu and edu != "不限":
        hard.append({"field": "学历", "requirement": edu})
    if exp and exp != "不限":
        hard.append({"field": "经验", "requirement": exp})
    seen = set()
    for sk in quals.get("certificates", []) + quals.get("hard_skills", []):
        if sk and sk not in seen:
            seen.add(sk)
            hard.append({"field": "技能", "requirement": sk})
    return hard


def _struct_boss(title: str, body: str) -> dict:
    user = f"岗位标题: {title}\n\nOCR 正文:\n{body[:1500]}"
    return chat_json(_SYSTEM_BOSS, user) or {}


def _structure(item: dict) -> dict:
    """对一条原始 item 做 LLM 结构化,返回最终 job。"""
    if item["source"] == "51job":
        user = f"工作职责:\n{item['responsibility']}\n\n任职资格:\n{item['qualification']}"
        llm = chat_json(_SYSTEM_51JOB, user) or {}
        quals = llm.get("qualifications", {}) or {}
        hard, resp = _clean_skill(
            _build_hard(item["edu"], item["exp"], quals),
            llm.get("responsibilities", []) or [],
        )
        return {
            "id": f"51job_{item['idx']:03d}", "source": "51job", "title": item["title"],
            "company": item["company"], "location": item["location"],
            "salary": parse_salary(item["salary"]), "job_type": item["job_type"],
            "responsibilities": resp,
            "qualifications": {
                "education": norm_edu(quals.get("education") or item["edu"] or ""),
                "major": quals.get("major") or [],
                "experience_years": quals.get("experience_years"),
                "certificates": quals.get("certificates") or [],
                "hard_skills": quals.get("hard_skills") or [],
                "soft_skills": quals.get("soft_skills") or [],
            },
            "hard": hard,
            "soft": item["keywords"],
            "benefits": item["benefits"],
            "keywords": item["keywords"],
            "raw": {"qualification": item["qualification"], "responsibility": item["responsibility"]},
        }
    else:
        llm = _struct_boss(item["title"], item["ocr"]) if item["ocr"] else {}
        quals = llm.get("qualifications", {}) or {}
        hard, resp = _clean_skill(
            _build_hard(item["edu"], item["exp"], quals),
            llm.get("responsibilities", []) or [],
        )
        return {
            "id": f"boss_{item['idx']:03d}", "source": "boss",
            "title": (llm.get("title") or item["title"]).strip(),
            "location": item["location"],
            "salary": parse_salary(item["salary"]), "job_type": item["job_type"],
            "responsibilities": resp,
            "qualifications": {
                "education": norm_edu(quals.get("education") or item["edu"] or ""),
                "major": quals.get("major") or [],
                "experience_years": quals.get("experience_years"),
                "certificates": quals.get("certificates") or [],
                "hard_skills": quals.get("hard_skills") or [],
                "soft_skills": quals.get("soft_skills") or [],
            },
            "hard": hard,
            "soft": [item["job_type"]],
            "raw": {"ocr": item["ocr"][:500]},
        }


def main(limit: int | None = None) -> None:
    base = Path(__file__).resolve().parent.parent
    raw = base / "data" / "jobs" / "raw"
    out = base / "data" / "jobs" / "jobs.json"

    items = raw_51job(str(raw / "前程无忧招聘信息汇总.csv"))
    items += raw_boss(str(raw / "hisense_boss_jobs_structured.md"))
    if limit:
        items = items[:limit]

    jobs = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for i, job in enumerate(pool.map(_structure, items), 1):
            jobs.append(job)
            if i % 20 == 0 or i == len(items):
                print(f"  进度 {i}/{len(items)}", flush=True)

    out.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")

    n = len(jobs)
    n_resp = sum(1 for j in jobs if j["responsibilities"])
    n_qual = sum(1 for j in jobs if any(j["qualifications"].values()))
    n_salary = sum(1 for j in jobs if j["salary"]["min"] is not None)
    print(f"✅ 结构化完成 {n} 条 → {out}")
    print(f"  有职责: {n_resp}/{n}  有任职资格: {n_qual}/{n}  有薪资: {n_salary}/{n}")
    print("来源:", dict(Counter(j["source"] for j in jobs)))

    for j in jobs:
        if j["source"] == "51job" and "品保" in j["title"]:
            print("\n样例(前程无忧·品保部长):", json.dumps(
                {k: j[k] for k in ("title", "salary", "responsibilities", "qualifications")},
                ensure_ascii=False, indent=2))
            break
    for j in jobs:
        if j["source"] == "boss" and "嵌入式" in j["title"]:
            print("\n样例(BOSS·嵌入式):", json.dumps(
                {k: j[k] for k in ("title", "salary", "responsibilities", "hard")},
                ensure_ascii=False, indent=2))
            break


if __name__ == "__main__":
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    main(limit)
