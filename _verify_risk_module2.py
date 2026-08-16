"""
验证脚本 · require.txt 模块2「风险识别与资质核验」补全
====================================================
用法：
    python _verify_risk_module2.py
覆盖：工作经历断层(Gap≥3月) / 证书过期(实际过期) / 简历造假(时间线重叠·矛盾) /
     核心技能真实性待核验 / 频繁跳槽 / 期望错位 —— 并回归 sample_resume 既有风险。
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))
from risk_filter import risk_report, detect_risks  # noqa: E402

BASE = pathlib.Path(__file__).resolve().parent
RAW = json.loads((BASE / "job_families_v2.json").read_text(encoding="utf-8"))
FAMILIES = RAW["job_families"] if isinstance(RAW, dict) and "job_families" in RAW else RAW
FAMILY_BY_KEY = {f["key"]: f for f in FAMILIES}


def show(title, resume, family_key=None):
    fam = FAMILY_BY_KEY.get(family_key) if family_key else None
    rep = risk_report(resume, fam)
    print(f"\n=== {title} · overall={rep['overall_level']} ===")
    for r in rep["risks"]:
        print(f"  [{r['level']}] {r['type']}: {r['detail']}")
        if r.get("advice"):
            print(f"        → 核验: {r['advice']}")
    return rep


def assert_types(title, rep, expected):
    got = {r["type"] for r in rep["risks"]}
    missing = [e for e in expected if e not in got]
    assert not missing, f"❌ {title} 缺少风险: {missing}"
    print(f"  ✅ {title} 命中预期风险: {expected}")


# 1) 回归：sample_resume（期望：证书核验 ×2 + 期望错位）
sample = json.loads((BASE / "sample_resume.json").read_text(encoding="utf-8"))
rep1 = show("回归 sample_resume", sample, "firstline")
assert_types("回归", rep1, {"证书核验", "期望错位"})

# 2) 断层 + 过期证书 + 技能无佐证（技术岗）
crafted = {
    "name": "候选人B",
    "education": {"degree": "本科", "major": "机械设计", "school": "X大学", "period": "2015-09 ~ 2019-06"},
    "work_experience": [
        {"company": "A", "position": "工艺员", "period": "2019-07 ~ 2021-02", "duration_years": 1.6,
         "duties": ["工序优化", "工艺控制"], "achievements": ["良率提升"]},
        {"company": "B", "position": "设备工程师", "period": "2021-07 ~ 2023-03", "duration_years": 1.8,
         "duties": ["设备维修"], "achievements": []},
    ],
    "skills": ["工序优化", "工装器具", "PLC"],
    "certificates": [{"name": "电工证", "expiry": "2024-01-01"}],
    "expected": {"target_position": "工艺工程师", "career_intention": "工艺工程师"},
}
rep2 = show("断层+过期证书+技能无佐证（工艺/设备岗）", crafted, "process-equipment")
assert_types("技术岗综合", rep2, {"工作经历断层", "证书过期", "核心技能真实性待核验"})

# 3) 简历造假：时间线重叠
overlap = {
    "name": "候选人C",
    "education": {"period": "2016-09 ~ 2020-06"},
    "work_experience": [
        {"company": "X", "period": "2020-07 ~ 2022-12", "duration_years": 2.5, "duties": ["a"], "achievements": []},
        {"company": "Y", "period": "2022-06 ~ 2023-06", "duration_years": 1.0, "duties": ["b"], "achievements": []},
    ],
    "skills": [], "certificates": [], "expected": {},
}
rep3 = show("简历造假：时间线重叠", overlap, "quality")
assert_types("时间线重叠", rep3, {"简历造假"})

# 4) 简历造假：首份工作早于毕业
contra = {
    "name": "候选人D",
    "education": {"period": "2018-09 ~ 2022-06"},
    "work_experience": [
        {"company": "Z", "period": "2021-01 ~ 2023-01", "duration_years": 2, "duties": ["x"], "achievements": []},
    ],
    "skills": [], "certificates": [], "expected": {},
}
rep4 = show("简历造假：工作早于毕业", contra, "quality")
assert_types("工作早于毕业", rep4, {"简历造假"})

# 5) 频繁跳槽（段数≥3 且均值<1年）
hop = {
    "name": "候选人E",
    "education": {},
    "work_experience": [
        {"company": "A", "period": "2020-01 ~ 2020-10", "duration_years": 0.8, "duties": [], "achievements": []},
        {"company": "B", "period": "2021-01 ~ 2021-11", "duration_years": 0.9, "duties": [], "achievements": []},
        {"company": "C", "period": "2022-02 ~ 2022-12", "duration_years": 0.9, "duties": [], "achievements": []},
    ],
    "skills": [], "certificates": [], "expected": {},
}
rep5 = show("频繁跳槽", hop, "firstline")
assert_types("频繁跳槽", rep5, {"频繁跳槽"})

print("\n✅ 全部断言通过：模块2 四类风险（断层/过期/造假/技能核验）均可确定性识别。")
