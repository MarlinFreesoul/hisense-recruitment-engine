"""
清理飞书模板示例数据 + 填入真实海信容声制造岗 + 真实简历
"""
import requests
import json

from config import FEISHU_APP_ID as APP_ID, FEISHU_APP_SECRET as APP_SECRET, FEISHU_BASE_TOKEN as BASE
JD_TABLE = "tblizVYaGfzcPBak"        # 招聘需求表
RESUME_TABLE = "tblNcaGuBlskCm8x"    # 简历库

BASE_URL = "https://open.feishu.cn/open-apis/bitable/v1/apps"


def token() -> str:
    r = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                      json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=30).json()
    return r["tenant_access_token"]


def headers(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def get_records(tok, table):
    records, pt = [], None
    while True:
        params = {"page_size": 100}
        if pt:
            params["page_token"] = pt
        r = requests.get(f"{BASE_URL}/{BASE}/tables/{table}/records", headers=headers(tok), params=params).json()
        records += r["data"]["items"]
        if r["data"].get("has_more"):
            pt = r["data"]["page_token"]
        else:
            break
    return records


def delete_records(tok, table, ids):
    if not ids:
        return {"code": 0, "msg": "nothing to delete"}
    r = requests.post(f"{BASE_URL}/{BASE}/tables/{table}/records/batch_delete",
                      headers=headers(tok), json={"records": ids}).json()
    return r


def create_records(tok, table, fields_list):
    r = requests.post(f"{BASE_URL}/{BASE}/tables/{table}/records/batch_create",
                      headers=headers(tok), json={"records": [{"fields": f} for f in fields_list]}).json()
    return r


# 真实海信容声制造岗 JD（来自 51job 调研数据）
REAL_JOBS = [
    {
        "岗位名称": "品保部长", "城市": "佛山顺德区",
        "岗位描述": "负责品质管理体系的建立、实施和维护；制定品质管理策略（质量控制/保证/改进）；监督生产过程质量控制；评估供应商质量；处理客户质量投诉；组织质量培训。",
        "任职资格": "本科及以上，机械工程/电子工程/质量管理等专业；5年以上家电品质管理经验；熟悉ISO9001/ISO14001；良好的问题分析与领导能力。",
        "当前状态": "招聘中",
    },
    {
        "岗位名称": "现场工艺工程师", "城市": "佛山顺德区",
        "岗位描述": "负责生产过程控制管理（机型定编、工序优化）；优化现场装配工艺、加工路线、操作方法；装配工位器具管理；工程不良问题改善。",
        "任职资格": "本科及以上，机械/电气/制冷等理工科；4年以上相关经验，家电行业优先；能吃苦耐劳、抗压，沟通协调能力强。",
        "当前状态": "招聘中",
    },
    {
        "岗位名称": "采购业务", "城市": "佛山顺德区",
        "岗位描述": "物料保障（月度采购订单、到货跟进）；资金占用控制；寻源开点及降成本；供应商月度评价。",
        "任职资格": "本科及以上，理工科优先；4年以上采购经验，家电行业优先；良好沟通协调能力、抗压应变能力。",
        "当前状态": "招聘中",
    },
    {
        "岗位名称": "设备专家", "城市": "佛山顺德区",
        "岗位描述": "非标自动化设备开发与方案评审；设备效率提升改造；设备故障排查与工程师培养。",
        "任职资格": "本科及以上，机械/电气类；6年以上家电设备经验；熟练PLC编程、单片机应用、电路控制。",
        "当前状态": "招聘中",
    },
    {
        "岗位名称": "装配工", "城市": "佛山顺德区",
        "岗位描述": "冰箱装配线日常装配（压缩机安装、管路连接、外壳装配）；产线点检维护；配合班组完成生产任务。",
        "任职资格": "学历不限；能接受两班倒；有制造业装配经验优先；吃苦耐劳、纪律性好。",
        "当前状态": "招聘中",
    },
]

# 真实简历（候选人A，一线装配工）
REAL_RESUME = [{
    "姓名": "候选人A",
    "最高学历": "大专",
    "毕业院校": "某职业技术学院",
    "工作年限": 3,
    "最近公司": "某家电制造有限公司",
    "最近职位": "装配工",
    "核心技能": ["装配", "电工", "钳工"],
    "工作经历简述": "冰箱装配线日常装配（压缩机安装、管路连接、外壳装配），装配效率提升10%，连续两年班组优秀员工，能吃苦耐劳，接受倒班安排。",
}]


def main():
    tok = token()

    # 1. 清理
    jd_records = get_records(tok, JD_TABLE)
    resume_records = get_records(tok, RESUME_TABLE)
    print(f"清理：JD表 {len(jd_records)} 条，简历表 {len(resume_records)} 条")

    r1 = delete_records(tok, JD_TABLE, [r["record_id"] for r in jd_records])
    r2 = delete_records(tok, RESUME_TABLE, [r["record_id"] for r in resume_records])
    print(f"删除 JD 表: code={r1.get('code')} | 删除简历表: code={r2.get('code')}")

    # 2. 填入真实岗位
    r3 = create_records(tok, JD_TABLE, REAL_JOBS)
    print(f"填入 {len(REAL_JOBS)} 个真实岗位: code={r3.get('code')}", r3.get('msg', ''))

    # 3. 填入真实简历
    r4 = create_records(tok, RESUME_TABLE, REAL_RESUME)
    print(f"填入 {len(REAL_RESUME)} 份真实简历: code={r4.get('code')}", r4.get('msg', ''))


if __name__ == "__main__":
    main()
