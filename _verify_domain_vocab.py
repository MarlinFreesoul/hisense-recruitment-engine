"""
离线验证：研发/制冷领域词库（P2）是否真实生效。
不触碰飞书/LLM；纯内存读取 JSON + 调用确定性引擎。
"""
from __future__ import annotations
import json
import pathlib
import sys

BASE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "src"))

passed = 0
failed = 0

def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")

# ---------- 1. JSON 结构 ----------
fams = json.loads((BASE / "job_families_v2.json").read_text(encoding="utf-8"))["job_families"]
rnd = next(f for f in fams if f["key"] == "rnd-engineering")
sds = rnd.get("sub_disciplines", [])
check("rnd 含 ≥10 个细分领域", len(sds) >= 10, f"got {len(sds)}")
roles = {sd["role"] for sd in sds}
need = {"制冷系统工程师", "结构工程师", "风道/流体工程师", "模具(Moldflow)工程师",
        "发泡工艺工程师", "电控/嵌入式工程师", "NVH/噪声工程师", "换热器工程师",
        "仿真(CAE)工程师", "整机/产品工程师"}
check("覆盖冰箱研发十大细分领域", need.issubset(roles), f"missing={need - roles}")
kw_count = sum(len(sd.get("keywords", [])) for sd in sds)
check("领域词库关键词总数 ≥ 60", kw_count >= 60, f"got {kw_count}")

# ---------- 2. 路由：制冷/结构/风道等标题 → rnd ----------
from matcher_v2 import match_job_family
route_cases = {
    "制冷系统工程师": "rnd-engineering",
    "冰箱结构工程师": "rnd-engineering",
    "风道流体工程师": "rnd-engineering",
    "NVH噪声工程师": "rnd-engineering",
    "换热器设计工程师": "rnd-engineering",
    "电控嵌入式工程师": "rnd-engineering",
    "Moldflow模流工程师": "rnd-engineering",   # 仿真型模具工程师 → 研发
    "冰箱整机产品工程师": "rnd-engineering",
}
for title, expect in route_cases.items():
    got = match_job_family(title)
    check(f"路由「{title}」→ rnd", got == expect, f"got {got}")

# 反向：不应被错路由到工艺/一线
check("「质检员」仍路由 quality", match_job_family("质检员") == "quality")
check("「装配工」仍路由 firstline", match_job_family("装配工") == "firstline")
check("「模具工程师」(裸模具) 路由 process-equipment", match_job_family("模具工程师") == "process-equipment")

# ---------- 3. 专业映射：制冷/材料 → 研发 ----------
maj = json.loads((BASE / "major_job_mapping.json").read_text(encoding="utf-8"))
def families_for_major(major):
    for g in maj["major_groups"]:
        if any(k in major for k in g["keywords"]):
            return set(g["job_families"])
    return set()
check("制冷及低温工程 → 研发", "研发/工程技术" in families_for_major("制冷及低温工程"))
check("高分子材料 → 研发", "研发/工程技术" in families_for_major("高分子材料"))

# ---------- 4. JD 生成含领域词库 ----------
from jd_generator import generate_jd
jd = generate_jd("rnd-engineering", {"position": "制冷系统工程师", "salary": "30-45K/月"})
check("JD 含 domain_sub_disciplines", len(jd.get("domain_sub_disciplines", [])) >= 10)
check("JD 职位名正确", jd["position"] == "制冷系统工程师")

# ---------- 5. 风险核验：领域词被真实消费 ----------
from risk_filter import detect_risks
rnd_resume = {
    "name": "测试研发",
    "education": {"degree": "本科", "major": "制冷及低温工程"},
    "skills": ["制冷系统", "CFD", "Moldflow"],   # 主张 3 个领域词
    "work_experience": [{
        "position": "制冷工程师",
        "period": "2020-07 ~ 至今",
        "duration_years": 4,
        "duties": ["负责制冷系统匹配与充注量优化"],   # 仅佐证 制冷系统
        "achievements": [],
    }],
    "certificates": [],
    "expected": {"available_date": "1个月内", "career_intention": "研发", "target_position": "制冷系统工程师"},
    "self_evaluation": "熟悉冰箱研发",
}
risks = detect_risks(rnd_resume, rnd)
auth = [r for r in risks if r["type"] == "核心技能真实性待核验"]
flagged = {r["detail"].split("「")[1].split("」")[0] for r in auth}
check("CFD 因无佐证被标真实性待核验", "CFD" in flagged, f"flagged={flagged}")
check("Moldflow 因无佐证被标真实性待核验", "Moldflow" in flagged, f"flagged={flagged}")
check("制冷系统 有佐证不被误标", "制冷系统" not in flagged, f"flagged={flagged}")

# ---------- 6. 面试题库含 rnd ----------
bank = json.loads((BASE / "interview_question_bank.json").read_text(encoding="utf-8"))
rnd_bank = next((b for b in bank["banks"] if b["key"] == "rnd-engineering"), None)
check("面试题库含 rnd-engineering", rnd_bank is not None)
if rnd_bank:
    dims = {d["dim"] for d in rnd_bank["dimensions"]}
    check("rnd 题库含 制冷系统设计/风道流体/电控嵌入式 维度",
          {"制冷系统设计", "风道流体", "电控/嵌入式"}.issubset(dims), f"got={dims}")

# ---------- 7. 打分引擎对 rnd 不报错 ----------
from scoring import compute_match
score = compute_match(rnd_resume, rnd)
check("compute_match(rnd) 产出 match_score", score.get("match_score") is not None,
      f"score={score.get('match_score')}")

print(f"\n结果：{passed} 通过 / {failed} 失败")
sys.exit(1 if failed else 0)
