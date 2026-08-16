"""
离线冒烟测试：验证 P0#1 / P0#2 / P1#3 补全是否生效（不触发真实飞书/LLM 写）。
运行：受管 venv python _verify_mvp_gaps.py
"""
from __future__ import annotations
import os
import sys
import tempfile
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ---- 关闭所有外部写入，确保纯离线 ----
import config
config.RESULT_TABLE_ID = ""
config.TALENT_POOL_TABLE_ID = ""
config.JD_TABLE_ID = ""
config.RESUME_TABLE_ID = ""
config.INTERVIEW_TABLE_ID = ""
config.DEEPSEEK_API_KEY = ""          # 强制走离线正则解析
os.environ["FEISHU_BOT_WEBHOOK"] = ""  # 关闭群机器人推送

from fastapi.testclient import TestClient
import api.server as srv
from src.interview_collect import generate_core_questions

client = TestClient(srv.app)

PASS, FAIL = 0, 0


def check(name: str, cond: bool, extra: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name} {extra}")
    else:
        FAIL += 1
        print(f"  ✗ {name} {extra}")


print("== P0#1 真实简历上传 + 自动入池 ==")
resume_txt = (
    "姓名：测试员王五\n"
    "本科，机械制造专业，4 年装配经验，持有电工证，接受倒班，随时到岗。"
)
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
    f.write(resume_txt)
    tmp = f.name

with open(tmp, "rb") as fh:
    r = client.post(
        "/screen/upload",
        files={"file": ("resume_王五.txt", fh, "text/plain")},
        data={"job_family": "firstline", "job_name": "装配包装工", "write_feishu": "false"},
    )
os.unlink(tmp)
body = r.json()
check("POST /screen/upload 返回 200", r.status_code == 200, f"(status={r.status_code})")
check("上传即打分 success=True", body.get("success") is True, str(body.get("error", "")))
res = body.get("result", {})
cid = body.get("candidate_id")
check("产出 0-100 匹配度", isinstance(res.get("匹配度"), (int, float)), f"匹配度={res.get('匹配度')}")
check("产出等级", bool(res.get("等级")), f"等级={res.get('等级')}")
check("自动入人才池 pooled=True", body.get("talent_pool", {}).get("pooled") is True)
check("返回 candidate_id", bool(cid), f"cid={cid}")

print("== 人才池可见该候选人 ==")
r = client.get("/talent-pool?job_family=firstline")
rows = r.json().get("comparison", [])
check("GET /talent-pool 含上传候选人", any(x.get("candidateId") == cid for x in rows), f"共 {len(rows)} 行")

print("== P0#2 HR↔用人部门 双向推送审批流 ==")
r = client.post("/review/department-push", json={"candidate_id": cid, "name": "测试员王五", "job_family": "firstline"})
bp = r.json()
check("POST /review/department-push success", bp.get("success") is True)
check("状态变为 待部门复核", bp.get("status") == "待部门复核", f"status={bp.get('status')}")

r = client.post("/review/department-decision", json={
    "candidate_id": cid, "name": "测试员王五", "job_family": "firstline",
    "decision": "通过", "note": "经验匹配，建议推进",
})
dp = r.json()
check("POST /review/department-decision success", dp.get("success") is True)
check("回写人才池状态=部门通过-待HR初面", dp.get("pool_status") == "部门通过-待HR初面", f"pool_status={dp.get('pool_status')}")
check("部门备注已记录", dp.get("record", {}).get("note") == "经验匹配，建议推进", f"note={dp.get('record', {}).get('note')}")

print("== 模块 4 Offer 放弃秒级递补（演示数据链） ==")
r = client.post("/demo/seed")
sd = r.json()
check("POST /demo/seed 灌入 6 份", sd.get("seeded") == 6, f"seeded={sd.get('seeded')}")
r = client.get("/talent-pool")
rows = r.json().get("comparison", [])
top = sorted(rows, key=lambda x: (x.get("totalScore") or 0), reverse=True)[0]
r = client.post("/decision/offer-fallback", json={"job_family": "firstline", "rejected_id": top["candidateId"]})
fb = r.json()
check("POST /decision/offer-fallback success", fb.get("success") is True)
check("推举出下一顺位 next_best", bool(fb.get("next_best")), f"next={fb.get('next_best', {}).get('name') if fb.get('next_best') else None}")
check("附带 fallback_reason", bool(fb.get("fallback_reason")))

print("== P1#3 测评报告 → 个性化追问 ==")
qs = generate_core_questions("firstline", {"certificates": [{"name": "电工证", "expiry": "未注明"}]}, [],
                             assessment_report="逻辑思维 72 分（待提升）；抗压 80 分")
has_assess = any(q.get("id") == "assessment_followup" for q in qs)
check("generate_core_questions 针对测评报告追加个性化问题", has_assess)
sample = next((q for q in qs if q.get("id") == "assessment_followup"), {})
check("追问文本含测评结论", "逻辑思维" in sample.get("问题", ""), sample.get("问题", "")[:30])

print(f"\n结果：通过 {PASS} 项，失败 {FAIL} 项")
sys.exit(1 if FAIL else 0)
