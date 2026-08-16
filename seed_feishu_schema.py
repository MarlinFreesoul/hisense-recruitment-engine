"""
补飞书字段 + 建评分结果表
1. 简历库补 4 字段：专业 / 证书 / 自我评价 / 期望到岗
2. 新建「评分结果表」+ 字段
"""
import requests

from config import FEISHU_APP_ID as APP_ID, FEISHU_APP_SECRET as APP_SECRET, FEISHU_BASE_TOKEN as BASE
RESUME_TABLE = "tblNcaGuBlskCm8x"

API = "https://open.feishu.cn/open-apis/bitable/v1/apps"


def token() -> str:
    r = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                      json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=30).json()
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
    r = requests.post(f"{API}/{BASE}/tables", headers=hdr(tok),
                      json={"table": {"name": name, "default_view_name": "全部"}}).json()
    return r


def main():
    tok = token()

    # 1. 简历库补 4 字段（文本类型）
    print("=== 补简历库字段 ===")
    for name in ["专业", "证书", "自我评价", "期望到岗"]:
        r = create_field(tok, RESUME_TABLE, name, 1)
        print(f"  {name}: code={r.get('code')} {r.get('msg', '')}")

    # 2. 建评分结果表
    print("\n=== 建评分结果表 ===")
    r = create_table(tok, "评分结果表")
    if r.get("code") == 0:
        new_table_id = r["data"]["table_id"]
        print(f"  评分结果表已建: {new_table_id}")
        fields = [
            ("候选人", 1, None),
            ("岗位名称", 1, None),
            ("匹配度", 2, None),
            ("等级", 3, ["A级", "B级", "C级", "不推荐"]),
            ("风险等级", 3, ["低", "中", "高"]),
            ("匹配总结", 1, None),
            ("推荐结论", 3, ["通过筛选", "待定", "淘汰"]),
        ]
        for name, ftype, opts in fields:
            rr = create_field(tok, new_table_id, name, ftype, opts)
            print(f"    {name}: code={rr.get('code')} {rr.get('msg', '')}")
        print(f"\n  ★ 评分结果表 table_id = {new_table_id}（记下这个，写进 matcher_v2）")
    else:
        print(f"  建表失败: {r}")


if __name__ == "__main__":
    main()
