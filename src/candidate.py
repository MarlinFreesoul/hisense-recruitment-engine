"""
视频面试 · 候选人身份与面试资格门禁
==================================
设计目标（用户明确要求）：
  1) 系统能区分飞书中不同的真实候选人，每个候选人都有独立、唯一的 ID，互不混淆；
  2) 确保每一次视频对话，都是真实候选人「填写完资料」之后，才可以被分配房间与 HR 面试。

实现：
  - 每个真实候选人 = 飞书「简历库」(RESUME_TABLE_ID) 的一条记录，其 record_id 即全局唯一 ID。
  - fetch_profile(record_id)         : 精准读取某候选人的真实简历记录。
  - is_eligible(record_id)           : 门禁校验（记录真实存在 + 必填字段已填）。
  - register_profile(fields, rid)    : 候选人「填写/修改资料」→ 新建或更新简历记录，返回唯一 ID。
  - 该 record_id 同时作为：TRTC 房间候选人 userId 前缀(cand_<id>)、COS 录制文件前缀、面试记录归属，
    全链路以此 ID 隔离，杜绝候选人彼此混淆。
"""
from __future__ import annotations

from config import RESUME_TABLE_ID, CANDIDATE_REQUIRED_FIELDS
from src.matcher_v2 import FeishuClient


def fetch_profile(record_id: str) -> dict | None:
    """按 record_id 精准读取飞书简历库记录，不存在返回 None。"""
    if not record_id:
        return None
    return FeishuClient().get_record(RESUME_TABLE_ID, record_id)


def missing_required(fields: dict) -> list:
    """返回候选人资料中缺失的必填字段清单。"""
    miss = []
    for f in CANDIDATE_REQUIRED_FIELDS:
        v = fields.get(f)
        if v in (None, "", [], {}):
            miss.append(f)
    return miss


def is_eligible(record_id: str) -> dict:
    """面试资格门禁：候选人必须是飞书简历库中的真实记录，且必填字段已填。

    返回 {eligible, reason, profile, missing}。
    """
    prof = fetch_profile(record_id)
    if not prof:
        return {
            "eligible": False,
            "reason": "候选人不存在，或不是飞书简历库中的真实记录（请先通过填写资料生成独立候选人 ID）",
            "profile": None,
            "missing": list(CANDIDATE_REQUIRED_FIELDS),
        }
    fields = prof.get("fields", {})
    miss = missing_required(fields)
    if miss:
        return {
            "eligible": False,
            "reason": f"候选人资料未填写完整，缺少：{', '.join(miss)}；请先完整填写简历后再预约面试",
            "profile": fields,
            "missing": miss,
        }
    return {
        "eligible": True,
        "reason": "候选人资料完整，具备视频面试资格",
        "profile": fields,
        "missing": [],
    }


def register_profile(fields: dict, record_id: str = None) -> dict:
    """候选人填写 / 修改资料。

    record_id 为空 → 在简历库新建一条记录（系统分配唯一 ID）；
    record_id 不为空 → 更新该记录（保留同一 ID，不新建），实现「修改资料」。
    返回 {record_id, eligible, missing, reason}。
    """
    feishu = FeishuClient()
    if record_id:
        feishu.update_record(RESUME_TABLE_ID, record_id, fields)
        rid = record_id
    else:
        r = feishu.create_records(RESUME_TABLE_ID, [fields])
        items = (r.get("data") or {}).get("records", [])
        rid = items[0]["record_id"] if items else None
    if not rid:
        return {"record_id": None, "eligible": False,
                "missing": list(CANDIDATE_REQUIRED_FIELDS),
                "reason": f"创建候选人记录失败：{r}"}
    elig = is_eligible(rid)
    return {
        "record_id": rid,
        "eligible": elig["eligible"],
        "missing": elig["missing"],
        "reason": elig["reason"],
    }


def candidate_user_id(record_id: str, interviewer_id: str = "hr") -> tuple:
    """返回本候选人在 TRTC 中的 userId 对：(candidate_user_id, hr_user_id)。

    与 src.video_room.create_room 保持一致：候选人 = cand_<id>，HR = hr_<interviewer_id>。
    文件录制后文件名含该 userId，后端据此按轨道标说话人。
    """
    return f"cand_{record_id}", f"hr_{interviewer_id}"


if __name__ == "__main__":
    # 自测需真实飞书；仅演示调用形态
    print("candidate 模块已加载。门禁必填字段：", CANDIDATE_REQUIRED_FIELDS)
