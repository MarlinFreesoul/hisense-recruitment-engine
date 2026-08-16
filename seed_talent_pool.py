"""
建「人才储备池」表（模块 4：合格候选人自动入库 + 分类标签 + Offer 递补）
=========================================================================
用法：
    python seed_talent_pool.py
建表成功后返回 table_id，把它填进 config.py 的 TALENT_POOL_TABLE_ID（或 .env）。

字段设计（对齐 PRD 模块 4）：
    候选人(text) / 岗位族(text) / 应聘岗位(text) / 匹配度(number)
    等级(text) / 风险等级(text) / 标签(text)
    状态(text: 储备/已发offer/已放弃offer/已入职) / 匹配总结(text) / 入库时间(text)

说明：等级/风险等级/状态 用「文本」而非单选 —— 与项目现有评分结果表(模块1)写飞书的方式一致
（screening.py 直接写字符串），避免 single_select 的 SingleSelectFieldConvFail。
"""
import requests

from config import FEISHU_APP_ID as APP_ID, FEISHU_APP_SECRET as APP_SECRET, FEISHU_BASE_TOKEN as BASE

API = "https://open.feishu.cn/open-apis/bitable/v1/apps"


def token() -> str:
    r = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                      json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=30).json()
    if r.get("code") != 0:
        raise RuntimeError(f"飞书鉴权失败: {r}")
    return r["tenant_access_token"]


def hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def create_field(tok, table, name, ftype, options=None):
    body = {"field_name": name, "type": ftype}
    if options:
        body["property"] = {"options": [{"name": o} for o in options]}
    r = requests.post(f"{API}/{BASE}/tables/{table}/fields", headers=hdr(tok), json=body).json()
    return r


def create_table(tok, name):
    # 飞书 v1 建表：body 为 {"table": {"name": ...}}；default_view_name 会导致 WrongRequestBody，故省略。
    r = requests.post(f"{API}/{BASE}/tables", headers=hdr(tok),
                      json={"table": {"name": name}}).json()
    return r


def main():
    tok = token()
    print("=== 建「人才储备池」表 ===")
    r = create_table(tok, "人才储备池")
    if r.get("code") != 0:
        print(f"  建表失败: {r}")
        return
    new_table_id = r["data"]["table_id"]
    print(f"  人才储备池已建: {new_table_id}")

    fields = [
        ("候选人", 1, None),
        ("岗位族", 1, None),
        ("应聘岗位", 1, None),
        ("匹配度", 2, None),
        ("等级", 1, None),
        ("风险等级", 1, None),
        ("标签", 1, None),
        ("状态", 1, None),
        ("匹配总结", 1, None),
        ("入库时间", 1, None),
    ]
    for name, ftype, opts in fields:
        rr = create_field(tok, new_table_id, name, ftype, opts)
        print(f"    {name}: code={rr.get('code')} {rr.get('msg', '')}")

    print(f"\n  ★ 人才储备池 table_id = {new_table_id}")
    print(f"  → 写进 config.py：TALENT_POOL_TABLE_ID = \"{new_table_id}\"")
    print(f"  → 或写进 .env：TALENT_POOL_TABLE_ID={new_table_id}")


if __name__ == "__main__":
    main()
