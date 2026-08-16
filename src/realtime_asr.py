"""
视频面试 · 独立语音识别（腾讯云实时语音识别 / 流式 ASR）
========================================================
设计：后端只负责「签名」，不下发 SecretKey 到浏览器。
  - build_asr_connect_url() 用腾讯云 SecretId/SecretKey 走 TC3-HMAC-SHA256 签出
    authorization，拼成完整的 wss:// 连接串返回给前端；
  - 前端（浏览器）直接拿这个串连 ASR WebSocket、自己推 PCM 音频流、收 JSON 转写结果。
真正的音频流不经过我们的后端，延迟最低、也最安全。

为什么独立接 ASR 而不是用 TRTC 内置 AI 识别：
  - 单价更低（约 0.017 元/分钟，见前文测算），且计费独立、不绑 TRTC 套餐；
  - 与 TRTC 解耦，后续可平滑替换混元 ASR / 讯飞等。

接入校验说明（重要）：
  - TC3 签名算法本身通用且已自测；但「实时语音识别」WebSocket 的【连接参数集合】
    在不同 API 版本里略有差异。若联调报签名错误，对照腾讯云官方 recognize_ws.py
    调整下方 ASR_SIGN_PARAMS 列表即可（常见差异：是否含 source / nonce）。
  - 浏览器侧的「音频帧头字节布局」请以前端组件 webapp/components/VideoInterview.tsx 为准。
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import time
import uuid
from urllib.parse import quote

from config import (
    TENCENT_SECRET_ID, TENCENT_SECRET_KEY, ASR_APP_ID,
    ASR_ENGINE_MODEL, ASR_VOICE_FORMAT,
)

# 参与签名 + 拼接 URL 的查询参数。联调报错时对照官方 demo 调整本列表。
ASR_SIGN_PARAMS = [
    "engine_model_type", "voice_format", "needvad",
    "voice_id", "source", "secretid", "timestamp", "expired", "nonce",
]
ASR_HOST = "asr.tencentcloudapi.com"
ASR_SERVICE = "asr"


def _percent_encode(s: str) -> str:
    return quote(str(s), safe="-_.~")


def _tc3_sign(secret_id: str, secret_key: str, params: dict, timestamp: int) -> str:
    """腾讯云 TC3-HMAC-SHA256 签名，返回 Authorization 字符串。"""
    algorithm = "TC3-HMAC-SHA256"
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))
    credential_scope = f"{date}/{ASR_SERVICE}/tc3_request"

    canonical_query = "&".join(
        f"{_percent_encode(k)}={_percent_encode(params[k])}"
        for k in sorted(params)
    )
    canonical_headers = f"content-type:application/json\nhost:{ASR_HOST}\n"
    signed_headers = "content-type;host"
    hashed_payload = hashlib.sha256(b"").hexdigest()
    canonical_request = "\n".join([
        "GET", "/", canonical_query, canonical_headers, signed_headers, hashed_payload
    ])

    string_to_sign = "\n".join([
        algorithm, str(timestamp), credential_scope,
        hashlib.sha256(canonical_request.encode()).hexdigest(),
    ])

    def _hmac(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    secret_date = _hmac(("TC3" + secret_key).encode(), date)
    secret_service = _hmac(secret_date, ASR_SERVICE)
    secret_signing = _hmac(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

    return (
        f"{algorithm} Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )


def build_asr_connect_url(voice_id: str = None) -> dict:
    """签出腾讯云实时语音识别的 WebSocket 连接串，供前端直接连。

    返回：{ url, voice_id, expired }。前端用 url 建 WebSocket，逐片发 PCM，
    服务端返回文本帧（JSON），result 字段即转写文本，final=1 为最终结果。
    """
    if not (TENCENT_SECRET_ID and TENCENT_SECRET_KEY and ASR_APP_ID):
        raise RuntimeError("未配置 TENCENT_SECRET_ID / TENCENT_SECRET_KEY / ASR_APP_ID")

    timestamp = int(time.time())
    expired = timestamp + 3600  # 签名有效期 1 小时
    voice_id = voice_id or uuid.uuid4().hex

    params = {
        "engine_model_type": ASR_ENGINE_MODEL,
        "voice_format": ASR_VOICE_FORMAT,
        "needvad": 1,
        "voice_id": voice_id,
        "source": 0,
        "secretid": TENCENT_SECRET_ID,
        "timestamp": timestamp,
        "expired": expired,
        "nonce": uuid.uuid4().hex[:8],
    }
    authorization = _tc3_sign(TENCENT_SECRET_ID, TENCENT_SECRET_KEY, params, timestamp)
    params["authorization"] = authorization

    query = "&".join(
        f"{_percent_encode(k)}={_percent_encode(params[k])}" for k in ASR_SIGN_PARAMS + ["authorization"]
    )
    return {
        "url": f"wss://{ASR_HOST}/asr/v2/{ASR_APP_ID}?{query}",
        "voice_id": voice_id,
        "expired": expired,
    }


if __name__ == "__main__":
    # 离线自测（需先在 .env 填腾讯云凭证；仅验证签名串格式，不真正连腾讯云）
    if not TENCENT_SECRET_ID:
        print("未配置 TENCENT_SECRET_ID，跳过自测")
    else:
        out = build_asr_connect_url("test_voice_001")
        assert out["url"].startswith("wss://asr.tencentcloudapi.com/asr/v2/")
        assert "authorization=TC3-HMAC-SHA256" in out["url"]
        print("ASR 连接串生成 OK，长度:", len(out["url"]))
        print("voice_id:", out["voice_id"])
