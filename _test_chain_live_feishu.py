"""
真对接飞书 · 端到端验证（含精准清理）
====================================
链路：建/复用「人才储备池」表 → 上传即打分(离线解析) + 自动入池(写飞书)
      → 触发 Offer 放弃(改飞书状态) → 精准删除测试记录(by record_id)。

安全约定：
- 仅用真实飞书凭证写几条测试记录到一张 demo 表。
- 全程收集 record_id，finally 中按 id 精准删除，绝不整表清空(clear_table)。
- 不写「评分结果表」(RESULT_TABLE_ID 置空)，不触发群机器人(webhook 为空)。
"""
import os
import requests

from config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_BASE_TOKEN

API = "https://open.feishu.cn/open-apis/bitable/v1/apps"
TABLE_NAME = "人才储备池_demo"


def _tok():
    r = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                      json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}, timeout=30).json()
    if r.get("code") != 0:
        raise RuntimeError(f"飞书鉴权失败: {r}")
    return r["tenant_access_token"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=utf-8"}


def get_or_create_table(tok):
    # 若已存在同名表则复用（避免 TableNameDuplicated），否则新建（text 字段）
    lst = requests.get(f"{API}/{FEISHU_BASE_TOKEN}/tables", headers=_hdr(tok),
                       params={"page_size": 100}, timeout=30).json()
    for t in lst.get("data", {}).get("items", []):
        if t.get("name") == TABLE_NAME:
            print(f"    复用已存在表 table_id = {t['table_id']}")
            return t["table_id"]
    r = requests.post(f"{API}/{FEISHU_BASE_TOKEN}/tables", headers=_hdr(tok),
                      json={"table": {"name": TABLE_NAME}}, timeout=30).json()
    if r.get("code") != 0:
        raise RuntimeError(f"建表失败: {r}")
    tid = r["data"]["table_id"]
    fields = [("候选人", 1), ("岗位族", 1), ("应聘岗位", 1), ("匹配度", 2),
              ("等级", 1), ("风险等级", 1), ("标签", 1), ("状态", 1),
              ("匹配总结", 1), ("入库时间", 1)]
    for name, ftype in fields:
        requests.post(f"{API}/{FEISHU_BASE_TOKEN}/tables/{tid}/fields",
                      headers=_hdr(tok), json={"field_name": name, "type": ftype}, timeout=30).json()
    print(f"    新建表 table_id = {tid}")
    return tid


def main():
    # ---- 仅允许真实飞书；其余变量清理，避免污染 ----
    os.environ["DEEPSEEK_API_KEY"] = ""
    os.environ["RESULT_TABLE_ID"] = ""
    os.environ["FEISHU_BOT_WEBHOOK"] = ""

    tok = _tok()
    new_table = get_or_create_table(tok)

    import config as _cfg
    _cfg.TALENT_POOL_TABLE_ID = new_table

    from src.screening import screen_resume
    from src.talent_pool import get_pool
    from src.matcher_v2 import FeishuClient

    pool = get_pool()
    pool._by_id.clear()
    created_ids = []   # 精准清理清单（finally 中删除）

    try:
        print("\n[2] 上传即打分 + 自动入池（写飞书）")
        samples = [
            ("张三", "姓名：张三。本科，机械制造专业，8 年设备维修经验，持有电工证、钳工证，接受倒班，随时到岗。", "firstline", "设备维修工"),
            ("李四", "姓名：李四。大专，电气自动化，3 年装配经验，有叉车证，可接受夜班，一个月内到岗。", "firstline", "装配包装工"),
        ]
        for name, text, fam, job in samples:
            out = screen_resume(text=text, job_family=fam, job_name=job, write_feishu=True)
            tp = out["talent_pool"]
            rid = tp.get("feishu_record_id")
            if rid:
                created_ids.append(rid)
            print(f"    [{name}] 匹配度={out['result']['匹配度']} 等级={out['result']['等级']} "
                  f"| 入池={tp['pooled']} 飞书record_id={rid or '（未写回）'}")
            assert rid, f"❌ {name} 未写回飞书，集成失败"

        print("\n[3] 触发 Offer 放弃（改飞书状态）")
        top_id = pool.rank("firstline")[0].candidate_id
        out = pool.handle_offer_rejection("firstline", rejected_id=top_id)
        print("    递补理由：", out["fallback_reason"])
        print("    下一顺位：", out["next_best"]["name"] if out["next_best"] else None)

        fc = FeishuClient()
        rejected_rid = pool.get(top_id).feishu_record_id
        rec = fc.get_record(new_table, rejected_rid)
        print(f"    飞书回读 rejected 状态 = {rec['fields'].get('状态')}  ← 应为「已放弃offer」")
        assert rec["fields"].get("状态") == "已放弃offer", "❌ 飞书状态未更新"
        next_rid = pool.get(out["next_best"]["candidateId"]).feishu_record_id
        rec2 = fc.get_record(new_table, next_rid)
        print(f"    飞书回读 next_best 状态 = {rec2['fields'].get('状态')}  ← 应为「已发offer」")
        assert rec2["fields"].get("状态") == "已发offer", "❌ 飞书递补状态未更新"
        print("    ✅ 飞书状态写回验证通过")

        print(f"\n🎉 真对接飞书端到端验证通过。demo 表 table_id = {new_table}")
        print("    → 正式使用请运行修复后的 seed_talent_pool.py 建「人才储备池」表，")
        print("      并将返回的 table_id 写入 config.TALENT_POOL_TABLE_ID / .env。")
    finally:
        # 精准清理本次写入的测试记录（绝不整表清空）
        if created_ids:
            try:
                FeishuClient().delete_records(new_table, created_ids)
                print(f"\n[cleanup] 已按 record_id 精准删除 {len(created_ids)} 条测试记录")
            except Exception as e:
                print(f"\n[cleanup] ⚠️ 清理失败，请手动删除 record_id: {created_ids}（错误：{e}）")
        else:
            print("\n[cleanup] 无测试记录需要清理")


if __name__ == "__main__":
    main()
