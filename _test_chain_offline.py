"""
离线验证：上传即打分 → 自动入人才池 → Offer 放弃秒级递补
不依赖飞书 / DeepSeek（全部走进程内内存池 + 离线解析兜底）。
"""
import os
# 关键：先把飞书/LLM 凭证置空，避免 config 的 _load_env(setdefault) 把 .env 真实值灌进来
os.environ.setdefault("FEISHU_APP_ID", "")
os.environ.setdefault("FEISHU_APP_SECRET", "")
os.environ.setdefault("FEISHU_BOT_WEBHOOK", "")
os.environ.setdefault("DEEPSEEK_API_KEY", "")
os.environ.setdefault("RESULT_TABLE_ID", "")
os.environ.setdefault("TALENT_POOL_TABLE_ID", "")

from src.screening import screen_resume
from src.talent_pool import get_pool

POOL = get_pool()
POOL._by_id.clear()  # 干净起步

# ---- 三份样例简历（离线正则解析）----
samples = [
    ("张三", "姓名：张三。本科，机械制造专业，8 年设备维修经验，持有电工证、钳工证，接受倒班，随时到岗。", "firstline", "设备维修工"),
    ("李四", "姓名：李四。大专，电气自动化，3 年装配经验，有叉车证，可接受夜班，一个月内到岗。", "firstline", "装配包装工"),
    ("王五", "姓名：王五。中专，机电，1 年质检经验，无证书，暂不接受倒班。", "firstline", "装配包装工"),
    ("赵六", "姓名：赵六。硕士，机械工程，6 年工艺装备设计，会 CAD、PLC，随时到岗。", "process-equipment", "工艺装备工程师"),
]

print("=" * 60)
print("阶段一：上传即打分 + 自动入池")
print("=" * 60)
for name, text, fam, job in samples:
    out = screen_resume(text=text, job_family=fam, job_name=job, write_feishu=False)
    r = out["result"]
    tp = out["talent_pool"]
    print(f"[{name}] 匹配度={r['匹配度']} 等级={r['等级']} 风险={r['风险等级']} "
          f"| 入池={tp['pooled']} 状态={tp['status']} 标签={tp['tags']} id={tp['candidate_id']}")

# ---- firstline 对比表 ----
print("\n" + "=" * 60)
print("阶段二：firstline 人才池对比表（按匹配度降序）")
print("=" * 60)
matrix = POOL.comparison_matrix("firstline")
for row in matrix:
    print(f"  {row['name']:<4} 分={row['totalScore']:<4} {row['grade']:<4} "
          f"风险{row['riskLevel']:<4} 状态={row['status']:<6} 标签={row['tags']}")

# ---- Offer 放弃递补 ----
print("\n" + "=" * 60)
print("阶段三：Offer 放弃 → 秒级递补（firstline，放弃第一名 张三）")
print("=" * 60)
top_id = matrix[0]["candidateId"]  # 张三（最高分）
out = POOL.handle_offer_rejection("firstline", rejected_id=top_id)
print("递补理由：", out["fallback_reason"])
print("下一顺位：", out["next_best"]["name"] if out["next_best"] else None, "| 已推送飞书：", out["feishu_pushed"])
print("递补后 firstline 对比表：")
for row in out["comparison"]:
    print(f"  {row['name']:<4} 分={row['totalScore']:<4} {row['grade']:<4} 状态={row['status']}")

# ---- 再次放弃（李四）→ 推王五 ----
print("\n阶段四：再次放弃李四 → 推王五")
li_id = next(r["candidateId"] for r in POOL.comparison_matrix("firstline") if r["name"] == "李四")
out2 = POOL.handle_offer_rejection("firstline", rejected_id=li_id)
print("递补理由：", out2["fallback_reason"])
print("下一顺位：", out2["next_best"]["name"] if out2["next_best"] else None)

# ---- 不指定 rejected_id（默认取 top1 已发offer 或 top1 可递补）----
print("\n阶段五：不指定 rejected_id，对 process-equipment 触发递补（仅赵六一人，应无可用递补）")
out3 = POOL.handle_offer_rejection("process-equipment")
print("触发：", out3["triggered"], "| 下一顺位：", out3["next_best"])
print("理由：", out3["fallback_reason"])

print("\n✅ 离线链路验证完成（全部走内存池，无飞书写操作）")
