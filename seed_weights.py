"""
建飞书「权重配置表」并写入默认权重 + 评分规则。
HR 在飞书里改「权重」列的数值，评分实时生效；「评分规则」列让每一分可审计。
"""
import requests
from config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_BASE_TOKEN as BASE

API = "https://open.feishu.cn/open-apis/bitable/v1/apps"


def token():
    r = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                      json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}, timeout=30).json()
    return r["tenant_access_token"]


def hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# 默认权重 + 评分规则（每一分怎么算）
WEIGHT_DATA = [
    # firstline 一线生产
    ("firstline", "稳定性", 0.30, "最近一段工作≥2年=10分，1-2年=7，0.5-1年=4，<0.5年=2；无经历=未知"),
    ("firstline", "软实力", 0.30, "命中关键词(吃苦/倒班/协作/团队/纪律/抗压/认真/责任/踏实)每个+2分，上限10；无自我评价=未知"),
    ("firstline", "经验", 0.20, "工作年限≥3=10分，1-3=7，<1=4；职位对口(家电/制造)+1；无经历=未知"),
    ("firstline", "技能", 0.20, "required命中率×6 + preferred命中×1 + 证书每个+1，上限10；无技能且无证书=未知"),
    # production-management 现场管理/管培
    ("production-management", "软实力", 0.40, "命中关键词每个+2分，上限10；无自我评价=未知"),
    ("production-management", "专业对口", 0.25, "专业大类→岗位族命中=10，不命中=3；专业缺失/无法判断=未知"),
    ("production-management", "经验", 0.20, "工作年限≥3=10，1-3=7，<1=4；职位对口+1；无经历=未知"),
    ("production-management", "技能", 0.15, "required命中率×6 + preferred×1 + 证书+1；无技能=未知"),
    # process-equipment 工艺/IE/设备
    ("process-equipment", "技能", 0.30, "required命中率×6 + preferred×1 + 证书+1；无技能=未知"),
    ("process-equipment", "专业对口", 0.30, "专业大类→岗位族命中=10，不命中=3；专业缺失=未知"),
    ("process-equipment", "经验", 0.20, "工作年限≥3=10，1-3=7，<1=4；职位对口+1；无经历=未知"),
    ("process-equipment", "软实力", 0.20, "命中关键词每个+2，上限10；无自我评价=未知"),
    # quality 质量
    ("quality", "技能", 0.30, "required命中率×6 + preferred×1 + 证书+1；无技能=未知"),
    ("quality", "专业对口", 0.25, "专业大类→岗位族命中=10，不命中=3；专业缺失=未知"),
    ("quality", "经验", 0.25, "工作年限≥3=10，1-3=7，<1=4；职位对口+1；无经历=未知"),
    ("quality", "软实力", 0.20, "命中关键词每个+2，上限10；无自我评价=未知"),
    # procurement-logistics 采购物流
    ("procurement-logistics", "专业对口", 0.25, "专业大类→岗位族命中=10，不命中=3；专业缺失=未知"),
    ("procurement-logistics", "技能", 0.25, "required命中率×6 + preferred×1 + 证书+1；无技能=未知"),
    ("procurement-logistics", "经验", 0.25, "工作年限≥3=10，1-3=7，<1=4；职位对口+1；无经历=未知"),
    ("procurement-logistics", "软实力", 0.25, "命中关键词每个+2，上限10；无自我评价=未知"),
    # rnd-engineering 研发
    ("rnd-engineering", "技能", 0.35, "required命中率×6 + preferred×1 + 证书+1；无技能=未知"),
    ("rnd-engineering", "专业对口", 0.25, "专业大类→岗位族命中=10，不命中=3；专业缺失=未知"),
    ("rnd-engineering", "经验", 0.25, "工作年限≥3=10，1-3=7，<1=4；职位对口+1；无经历=未知"),
    ("rnd-engineering", "软实力", 0.15, "命中关键词每个+2，上限10；无自我评价=未知"),
]


def main():
    tok = token()

    # 1. 建表
    r = requests.post(f"{API}/{BASE}/tables", headers=hdr(tok),
                      json={"table": {"name": "权重配置表"}}).json()
    if r.get("code") != 0:
        print(f"建表失败: {r}")
        return
    table_id = r["data"]["table_id"]
    print(f"✅ 权重配置表已建: {table_id}")

    # 2. 建字段
    fields = [
        ("岗位族", 1, None),
        ("维度", 1, None),
        ("权重", 2, None),
        ("评分规则", 1, None),
    ]
    for name, ftype, opts in fields:
        body = {"field_name": name, "type": ftype}
        requests.post(f"{API}/{BASE}/tables/{table_id}/fields", headers=hdr(tok), json=body)

    # 3. 写默认权重数据
    records = [{"fields": {"岗位族": k, "维度": d, "权重": w, "评分规则": rule}}
               for k, d, w, rule in WEIGHT_DATA]
    r = requests.post(f"{API}/{BASE}/tables/{table_id}/records/batch_create",
                      headers=hdr(tok), json={"records": records}).json()
    print(f"✅ 写入 {len(records)} 条权重: code={r.get('code')} {r.get('msg', '')}")
    print(f"\n★ 权重配置表 table_id = {table_id}（写进 config.py 的 WEIGHT_TABLE_ID）")


if __name__ == "__main__":
    main()
