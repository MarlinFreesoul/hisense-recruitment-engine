"""
海信 AI 招聘智能体 · 飞书接入（标准 API 封装）
==============================================
把筛选结果写入飞书多维表格 + 群机器人推送。

配置（环境变量或代码传参）：
    FEISHU_APP_ID / FEISHU_APP_SECRET  飞书开放平台应用凭证
    FEISHU_BOT_WEBHOOK                 群机器人 webhook（可选）
调用 add_bitable_record 需要多维表格的 app_token / table_id。
"""
import os
import requests


class FeishuClient:
    """飞书开放平台客户端。"""

    def __init__(self, app_id=None, app_secret=None):
        self.app_id = app_id or os.getenv("FEISHU_APP_ID", "")
        self.app_secret = app_secret or os.getenv("FEISHU_APP_SECRET", "")
        self._token = None

    def _tenant_token(self) -> str:
        if not self.app_id or not self.app_secret:
            raise RuntimeError("未配置 FEISHU_APP_ID / FEISHU_APP_SECRET，无法鉴权")
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": self.app_id, "app_secret": self.app_secret}, timeout=10)
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书鉴权失败: {data}")
        return data["tenant_access_token"]

    @property
    def token(self) -> str:
        if not self._token:
            self._token = self._tenant_token()
        return self._token

    def add_bitable_record(self, app_token: str, table_id: str, fields: dict) -> dict:
        """写入多维表格一条记录。fields 键为表格列名，值为单元格内容。"""
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        resp = requests.post(url, headers=headers, json={"fields": fields}, timeout=10)
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"写入多维表格失败: {data}")
        return data["data"]["record"]

    def send_bot_text(self, webhook: str, text: str) -> dict:
        """群机器人发送文本。"""
        resp = requests.post(webhook, json={"msg_type": "text", "content": {"text": text}}, timeout=10)
        return resp.json()


def push_screening_result(result: dict, app_token: str = None, table_id: str = None) -> dict:
    """把单份筛选结果推送到飞书（多维表格 + 机器人）。"""
    client = FeishuClient()
    match = result["match"]
    record = {
        "候选人": result.get("resume", {}).get("name", ""),
        "岗位": result["jd"]["position"],
        "匹配度": match["match_score"],
        "等级": match["grade"],
        "风险": result["risk"]["overall_level"],
        "推荐": result["recommendation"],
    }
    if app_token and table_id:
        client.add_bitable_record(app_token, table_id, record)
    webhook = os.getenv("FEISHU_BOT_WEBHOOK", "")
    if webhook:
        client.send_bot_text(webhook, f"新候选人评分：{record['候选人']} → {record['匹配度']}分（{record['等级']}）")
    return record


if __name__ == "__main__":
    # 自测（无凭证会抛错，属预期）
    print(push_screening_result({"jd": {"position": "装配包装工"}, "match": {"match_score": 98, "grade": "A级"},
                                 "risk": {"overall_level": "中"}, "recommendation": "通过",
                                 "resume": {"name": "候选人A"}}))
