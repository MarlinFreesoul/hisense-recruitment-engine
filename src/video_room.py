"""
视频面试 · TRTC 房间与 UserSig 签发
=================================
腾讯云 TRTC 走「独立接入」：后端只负责用 SDKAppID + 密钥 签发 UserSig，
真正的音视频流由前端（TRTC Web SDK）直连 TRTC，不经过本服务器。

UserSig 采用腾讯云 TLSSigAPIv2 算法（HMAC-SHA256，无第三方依赖），
算法与官方 trtc-python SDK 的 gen_sig 完全一致，可直接对拍验证。
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import random
import time

from config import TRTC_APP_ID, TRTC_SECRET_KEY, TRTC_USER_SIG_EXPIRE


def generate_user_sig(userid: str, sdkappid: str = None, key: str = None, expire: int = None) -> str:
    """签发 TRTC UserSig（TLSSigAPIv2）。

    userid 在房间内需唯一，建议用「候选人record_id」或「hr工号」做为标识。
    """
    sdkappid = str(sdkappid or TRTC_APP_ID)
    key = key or TRTC_SECRET_KEY
    expire = expire or TRTC_USER_SIG_EXPIRE
    if not sdkappid or not key:
        raise RuntimeError("未配置 TRTC_APP_ID / TRTC_SECRET_KEY，无法签发 UserSig")

    ts = int(time.time())
    b64_userid = base64.b64encode(userid.encode("utf-8")).decode("utf-8")
    content = (
        f"TLS.identifier:{b64_userid}\n"
        f"TLS.sdkappid:{sdkappid}\n"
        f"TLS.time:{ts}\n"
        f"TLS.expire:{expire}\n"
    )
    sig = hmac.new(key.encode("utf-8"), content.encode("utf-8"), hashlib.sha256).digest()
    payload = {
        "TLS.ver": "2.0",
        "TLS.identifier": b64_userid,
        "TLS.sdkappid": int(sdkappid),
        "TLS.time": ts,
        "TLS.expire": expire,
        "TLS.sig": base64.b64encode(sig).decode("utf-8"),
    }
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def create_room(candidate_id: str, interviewer_id: str = "hr", room_id: int = None) -> dict:
    """为一个「候选人 + 面试官」配对创建视频房间，返回双方入场所需凭据。

    返回的 room_id / user_sig / sdk_app_id 直接交给前端 TRTC Web SDK 使用。
    """
    sdkappid = TRTC_APP_ID
    if not sdkappid:
        raise RuntimeError("未配置 TRTC_APP_ID")
    if room_id is None:
        # TRTC 数字房间号上限 2^31-1；用候选人与随机盐避免碰撞
        room_id = random.randint(1, 2_000_000_000)

    return {
        "sdk_app_id": int(sdkappid),
        "room_id": room_id,
        "candidate": {
            "user_id": f"cand_{candidate_id}",
            "user_sig": generate_user_sig(f"cand_{candidate_id}"),
        },
        "interviewer": {
            "user_id": f"hr_{interviewer_id}",
            "user_sig": generate_user_sig(f"hr_{interviewer_id}"),
        },
        "expire_sec": TRTC_USER_SIG_EXPIRE,
    }


if __name__ == "__main__":
    # 离线自测（需先在 .env 填 TRTC_APP_ID / TRTC_SECRET_KEY）
    if not TRTC_APP_ID:
        print("未配置 TRTC_APP_ID / TRTC_SECRET_KEY，跳过自测")
    else:
        sig = generate_user_sig("cand_test")
        print("UserSig 样例（前 80 字符）:", sig[:80], "...")
        room = create_room("rec_123")
        print("房间信息:", json.dumps(room, ensure_ascii=False, indent=2))
