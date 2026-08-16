"""
视频面试 · TRTC 云端录制控制
===========================
面试进行中由后端启动「云端录制」（一个服务端机器人 rec_bot 进房录制），
结束停止录制。录制产物（音频）落腾讯云 COS，作为 asr_file 文件识别的输入，
进而产出带说话人分离的权威双人转写 + 面试评分（赛题模块 3 硬要求）。

与 realtime_asr / asr_file 的关系：
  - 实时：HR 一路流式 ASR 做现场辅助（低延迟、便宜）；
  - 事后：TRTC 云端录制 → 文件识别（带说话人分离）→ 权威纪要 + 评分。

安全：TRTC SDKAppID/密钥 仅后端使用；录制机器人 UserSig 也只在后端签发。
API 参考：腾讯云 TRTC CreateCloudRecording / DeleteCloudRecording / DescribeCloudRecording
         （trtc.tencentcloudapi.com, 2019-07-22）
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import time

import requests

from config import (
    ASR_FILE_REGION,
    COS_BUCKET,
    COS_REGION,
    TENCENT_SECRET_ID,
    TENCENT_SECRET_KEY,
    TRTC_APP_ID,
    TRTC_RECORD_BOT_USER,
    TRTC_RECORD_MODE,
    TRTC_RECORD_STORAGE,
    TRTC_SECRET_KEY,
)
from src.video_room import generate_user_sig


TRTC_HOST = "trtc.tencentcloudapi.com"
TRTC_VERSION = "2019-07-22"
TRTC_REGION = ASR_FILE_REGION  # 录制控制接口与文件识别同区域即可


# ---------- 单流录制文件名 ↔ UserId 互转 ----------
# TRTC 单流录制（不设置 MixTranscodeParams 即为单流）为每个用户生成独立文件，
# 文件名形如：<FileNamePrefix>/<TaskId>/<SdkAppId>_<RoomId>_<b64(UserId)>_s_<mediaType>_<start>_<end>.mp3
# 其中 UserId 先 base64，再把 '/'→'-'、'='→'.'。据此可从文件名反解说话人身份，
# 实现「按轨道标说话人」，无需依赖说话人分离。

def userid_to_filename_token(userid: str) -> str:
    """生成单流录制文件名中的 base64(UserId) 段（与 TRTC 规则一致）。"""
    b = base64.b64encode(userid.encode("utf-8")).decode("ascii")
    return b.replace("/", "-").replace("=", ".")


def _try_b64_decode(seg: str) -> str | None:
    """尝试把文件名段反解为 UserId（兼容 TRTC 的 '-'/'.' 替换）。"""
    s = seg.replace("-", "/").replace(".", "=")
    # 补齐 base64 padding
    s += "=" * (-len(s) % 4)
    try:
        dec = base64.b64decode(s).decode("utf-8")
    except Exception:
        return None
    if dec and (dec.startswith("cand_") or dec.startswith("hr_") or dec.startswith("rec_")):
        return dec
    return None


def parse_userid_from_filename(key: str) -> str | None:
    """从单流录制文件名反解 UserId。

    优先取文件名中第 3 个下划线分段（SdkAppId_RoomId_<b64uid>_...）；
    否则扫描所有分段尝试 base64 反解；最后兜底匹配 cand_/hr_ 字面串。
    """
    name = key.split("/")[-1].rsplit(".", 1)[0]
    parts = name.split("_")
    candidates = []
    if len(parts) >= 3:
        candidates.append(parts[2])
    candidates.extend(parts)
    for c in candidates:
        dec = _try_b64_decode(c)
        if dec:
            return dec
    # 兜底：文件名直接含 cand_/hr_ 字面
    for token in ("cand_", "hr_"):
        idx = name.find(token)
        if idx >= 0:
            return name[idx:].split(".")[0]
    return None


def parse_filename_timing(key: str) -> tuple:
    """从单流录制文件名解析该文件的全局起止时间（毫秒，UTC），用于双轨时间轴对齐。

    文件名末尾两段为 <start>_<end>（毫秒）。返回 (start_sec, end_sec)。
    """
    name = key.split("/")[-1].rsplit(".", 1)[0]
    parts = name.split("_")
    try:
        start = int(parts[-2])
        end = int(parts[-1])
        return start / 1000.0, end / 1000.0
    except (ValueError, IndexError):
        return 0.0, 0.0


# ---------- 腾讯云 TC3-HMAC-SHA256 签名（POST JSON） ----------

def _tc3_sign(action: str, payload: dict, region: str = TRTC_REGION):
    """返回 (authorization, timestamp, content_type)。无凭证时抛 RuntimeError。"""
    if not TENCENT_SECRET_ID or not TENCENT_SECRET_KEY:
        raise RuntimeError("未配置 TENCENT_SECRET_ID / TENCENT_SECRET_KEY，无法签名录制请求")
    algorithm = "TC3-HMAC-SHA256"
    timestamp = int(time.time())
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))
    content_type = "application/json; charset=utf-8"
    payload_str = json.dumps(payload, ensure_ascii=False)
    hashed_payload = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    canonical_headers = f"content-type:{content_type}\nhost:{TRTC_HOST}\n"
    signed_headers = "content-type;host"
    canonical_request = "\n".join([
        "POST", "/", "", canonical_headers, signed_headers, hashed_payload,
    ])
    credential_scope = f"{date}/trtc/tc3_request"
    hashed_cr = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = "\n".join([algorithm, str(timestamp), credential_scope, hashed_cr])

    def _hmac(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = _hmac(("TC3" + TENCENT_SECRET_KEY).encode("utf-8"), date)
    secret_service = _hmac(secret_date, "trtc")
    secret_signing = _hmac(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"{algorithm} Credential={TENCENT_SECRET_ID}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return authorization, timestamp, content_type


def _post(action: str, payload: dict, region: str = TRTC_REGION) -> dict:
    auth, ts, ct = _tc3_sign(action, payload, region)
    headers = {
        "Authorization": auth,
        "Content-Type": ct,
        "Host": TRTC_HOST,
        "X-TC-Action": action,
        "X-TC-Version": TRTC_VERSION,
        "X-TC-Timestamp": str(ts),
        "X-TC-Region": region,
    }
    resp = requests.post(
        f"https://{TRTC_HOST}/",
        headers=headers,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        timeout=30,
    )
    data = resp.json()
    if data.get("Response", {}).get("Error"):
        raise RuntimeError(f"{action} 失败: {data['Response']['Error']}")
    return data["Response"]


# ---------- 请求体构造（便于静态校验，不直接发网络） ----------

def build_start_params(room_id, bot_user_id: str = None, bot_user_sig: str = None,
                       *, sdk_app_id: str = None, record_mode: str = None,
                       storage: str = None) -> dict:
    """构造 CreateCloudRecording 请求体。

    room_id     : TRTC 房间号（整数或字符串均可，内部统一为字符串 + RoomIdType=0）
    bot_user_*  : 录制机器人进房身份（UserSig 由后端签）；不传则自动签一个
    record_mode : Audio / Video / VideoAndAudio（默认取配置 TRTC_RECORD_MODE）
    storage     : cos / vod（默认取配置 TRTC_RECORD_STORAGE）
    """
    sdk_app_id = int(sdk_app_id or TRTC_APP_ID)
    if not sdk_app_id:
        raise RuntimeError("未配置 TRTC_APP_ID")
    bot_user_id = bot_user_id or TRTC_RECORD_BOT_USER
    if bot_user_sig is None:
        bot_user_sig = generate_user_sig(bot_user_id)
    record_mode = (record_mode or TRTC_RECORD_MODE).capitalize()
    storage = (storage or TRTC_RECORD_STORAGE).lower()

    record_params = {
        "RecordMode": record_mode,   # 仅音频最省，且正是 ASR 所需
        "StreamType": 0,             # 0=只录制视频流中大流（音频含在内）
        "MaxIdleTime": 30,           # 房间空闲 30s 自动停止
        # 注意：不设置 MixTranscodeParams 即为「单流录制」——房间内每个用户(HR/候选人)
        # 各生成独立音频文件，文件名含 base64(UserId)，后端按轨道直接标说话人。
        # （TRTC_RECORD_SINGLE_STREAM 仅作配置态标识，实际由「无 MixTranscode」决定。）
    }

    if storage == "cos":
        if not (COS_BUCKET and COS_REGION and TENCENT_SECRET_ID and TENCENT_SECRET_KEY):
            raise RuntimeError("COS 存储模式需配置 COS_BUCKET / COS_REGION / 腾讯云凭证")
        storage_params = {
            "CloudStorage": {
                "Vendor": 0,                       # 0=腾讯云 COS
                "Region": COS_REGION,
                "Bucket": COS_BUCKET,
                "AccessKey": TENCENT_SECRET_ID,    # COS 写权限用的主账号 SecretId
                "SecretKey": TENCENT_SECRET_KEY,
                # 文件落盘路径前缀：<COS_RECORD_PREFIX><room_id>/...
                "FileNamePrefix": ["interview-records", str(room_id)],
            }
        }
    else:  # vod
        storage_params = {"CloudVod": {}}

    return {
        "SdkAppId": sdk_app_id,
        "RoomId": str(room_id),
        "RoomIdType": 0,                 # 0=数字房间号；1=字符串房间号
        "UserId": bot_user_id,
        "UserSig": bot_user_sig,
        "RecordParams": record_params,
        "StorageParams": storage_params,
    }


# ---------- 控制接口 ----------

def start_recording(room_id, bot_user_id: str = None, *, sdk_app_id: str = None,
                    record_mode: str = None, storage: str = None) -> dict:
    """启动 TRTC 云端录制，返回 {task_id, bot_user_id, params}。

    task_id 用于后续 stop / describe。
    """
    params = build_start_params(room_id, bot_user_id, None,
                                sdk_app_id=sdk_app_id, record_mode=record_mode, storage=storage)
    resp = _post("CreateCloudRecording", params)
    task_id = resp.get("TaskId")
    return {"task_id": task_id, "bot_user_id": params["UserId"], "params": params}


def stop_recording(task_id: str, *, sdk_app_id: str = None) -> dict:
    """停止云端录制（DeleteCloudRecording）。返回腾讯云响应。"""
    sdk_app_id = int(sdk_app_id or TRTC_APP_ID)
    if not sdk_app_id:
        raise RuntimeError("未配置 TRTC_APP_ID")
    if not task_id:
        raise ValueError("task_id 为空，无法停止录制")
    return _post("DeleteCloudRecording", {"SdkAppId": sdk_app_id, "TaskId": task_id})


def describe_recording(task_id: str, *, sdk_app_id: str = None) -> dict:
    """查询录制状态/结果（DescribeCloudRecording）。"""
    sdk_app_id = int(sdk_app_id or TRTC_APP_ID)
    if not sdk_app_id:
        raise RuntimeError("未配置 TRTC_APP_ID")
    if not task_id:
        raise ValueError("task_id 为空，无法查询")
    return _post("DescribeCloudRecording", {"SdkAppId": sdk_app_id, "TaskId": task_id})


if __name__ == "__main__":
    # 离线自测（需 TRTC 凭证）：仅校验请求体结构，不真正发起录制
    if not TRTC_APP_ID:
        print("未配置 TRTC_APP_ID，跳过自测")
    else:
        p = build_start_params(123456)
        assert p["RoomId"] == "123456" and p["RoomIdType"] == 0
        assert p["RecordParams"]["RecordMode"] in ("Audio", "Video", "VideoAndAudio")
        assert "CloudStorage" in p["StorageParams"]
        print("build_start_params OK:")
        print(json.dumps(p, ensure_ascii=False, indent=2))
