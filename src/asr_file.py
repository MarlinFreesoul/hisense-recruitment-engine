"""
视频面试 · 录音文件识别（腾讯云 ASR 文件识别，带说话人分离）
=========================================================
用于「事后权威纪要」：面试结束后，用 TRTC 云端录制或线下录音文件，
调腾讯云「录音文件识别」API（CreateRecTask + DescribeTaskStatus），
开启说话人分离（SpeakerDiarization），产出带说话人标签的双人转写。

与 realtime_asr.py（实时流式、单说话人）互补：
  - 实时：只 HR 一路，低延迟、便宜，做现场辅助；
  - 文件：异步、支持分离，做权威纪要 + 评分（赛题模块3硬要求）。

安全：SecretKey 仅后端使用，前端永不触达。
"""
from __future__ import annotations
import hashlib
import hmac
import json
import re
import time

import requests

from config import (
    ASR_APP_ID,
    ASR_FILE_ENGINE,
    ASR_FILE_REGION,
    TENCENT_SECRET_ID,
    TENCENT_SECRET_KEY,
)

FILE_ASR_HOST = "asr.tencentcloudapi.com"
FILE_ASR_VERSION = "2019-06-14"


# ---------- 腾讯云 TC3-HMAC-SHA256 签名（POST JSON） ----------

def _tc3_sign(action: str, payload: dict, region: str):
    """返回 (authorization, timestamp, content_type)。无凭证时抛 RuntimeError。"""
    if not TENCENT_SECRET_ID or not TENCENT_SECRET_KEY:
        raise RuntimeError("未配置 TENCENT_SECRET_ID / TENCENT_SECRET_KEY，无法签名文件识别请求")
    algorithm = "TC3-HMAC-SHA256"
    timestamp = int(time.time())
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))
    content_type = "application/json; charset=utf-8"
    payload_str = json.dumps(payload, ensure_ascii=False)
    hashed_payload = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    canonical_headers = f"content-type:{content_type}\nhost:{FILE_ASR_HOST}\n"
    signed_headers = "content-type;host"
    canonical_request = "\n".join([
        "POST", "/", "",
        canonical_headers, signed_headers, hashed_payload,
    ])
    credential_scope = f"{date}/asr/tc3_request"
    hashed_cr = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = "\n".join([algorithm, str(timestamp), credential_scope, hashed_cr])

    def _hmac(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = _hmac(("TC3" + TENCENT_SECRET_KEY).encode("utf-8"), date)
    secret_service = _hmac(secret_date, "asr")
    secret_signing = _hmac(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"{algorithm} Credential={TENCENT_SECRET_ID}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return authorization, timestamp, content_type


def _post(action: str, payload: dict, region: str = ASR_FILE_REGION) -> dict:
    auth, ts, ct = _tc3_sign(action, payload, region)
    headers = {
        "Authorization": auth,
        "Content-Type": ct,
        "Host": FILE_ASR_HOST,
        "X-TC-Action": action,
        "X-TC-Version": FILE_ASR_VERSION,
        "X-TC-Timestamp": str(ts),
        "X-TC-Region": region,
    }
    resp = requests.post(
        f"https://{FILE_ASR_HOST}/",
        headers=headers,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        timeout=30,
    )
    data = resp.json()
    if data.get("Response", {}).get("Error"):
        raise RuntimeError(f"{action} 失败: {data['Response']['Error']}")
    return data["Response"]


# ---------- 任务提交 / 轮询 ----------

def build_create_task_params(audio_url: str, *, engine_model_type: str = None,
                              voice_format: int = 1, speaker_diarization: bool = True) -> dict:
    """构造 CreateRecTask 请求体（便于单测校验，不直接发网络）。

    注意：录音文件识别的 CreateRecTask 不接收 VoiceFormat（接口自动识别音频格式），
    故此处不包含该字段；voice_format 仅保留作兼容性入参，不进入请求体。
    """
    return {
        "EngineModelType": engine_model_type or ASR_FILE_ENGINE,
        "ChannelNum": 1,
        "ResTextFormat": 1,            # 1=词级别详情，便于说话人分离
        "SourceType": 0,               # 0=URL；1=音频数据（base64 随请求提交）
        "Url": audio_url,
        "SpeakerDiarization": 1 if speaker_diarization else 0,
        "SpeakerNumber": 0,            # 0=自动判定说话人数量
    }


def create_recognition_task(audio_url: str, *, engine_model_type: str = None,
                            voice_format: int = 1, speaker_diarization: bool = True,
                            callback_url: str = None) -> int:
    """提交录音文件识别任务，返回 TaskId。audio_url 须为公网可访问地址。"""
    params = build_create_task_params(audio_url, engine_model_type=engine_model_type,
                                       voice_format=voice_format,
                                       speaker_diarization=speaker_diarization)
    if callback_url:
        params["CallbackUrl"] = callback_url
    resp = _post("CreateRecTask", params)
    return int(resp["Data"]["TaskId"])


def create_recognition_task_from_bytes(audio_bytes: bytes, *, engine_model_type: str = None,
                                       voice_format: int = 10,
                                       speaker_diarization: bool = False) -> int:
    """提交录音文件识别任务（SourceType=1）：音频直接随请求 base64 提交，<5MB，免公网托管。

    返回 TaskId。适用于本地生成/下载的音频（如 edge-tts 模拟、线下录音）直接走真实识别。
    注意：文件识别接口自动识别音频格式，不传 VoiceFormat。
    """
    import base64
    if not audio_bytes:
        raise ValueError("audio_bytes 为空，无法提交识别")
    params = {
        "EngineModelType": engine_model_type or ASR_FILE_ENGINE,
        "ChannelNum": 1,
        "ResTextFormat": 1,            # 词级别详情，便于后续解析
        "SourceType": 1,               # 1=音频数据随请求提交（base64，<5MB）
        "Data": base64.b64encode(audio_bytes).decode("ascii"),
        "SpeakerDiarization": 1 if speaker_diarization else 0,
        "SpeakerNumber": 0,
    }
    resp = _post("CreateRecTask", params)
    return int(resp["Data"]["TaskId"])


def recognize_bytes(audio_bytes: bytes, role: str, *, voice_format: int = 10,
                    engine_model_type: str = None, speaker_diarization: bool = False) -> list:
    """真实文件识别（SourceType=1）：提交→轮询→解析→整段标为同一角色。
    用于 HR / 候选人各自一路（单说话人）。"""
    task_id = create_recognition_task_from_bytes(
        audio_bytes, engine_model_type=engine_model_type,
        voice_format=voice_format, speaker_diarization=speaker_diarization)
    result = describe_task(task_id)
    result_str = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    segs = parse_result_to_segments(result_str)
    for s in segs:
        s["speaker"] = role
        s.pop("mock", None)
    return segs


def describe_task(task_id: int, *, poll: bool = True, max_wait: int = 600) -> dict:
    """查询任务结果，轮询至完成（Status==2）。返回 DescribeTaskStatus 的 Result 字典。"""
    deadline = time.time() + max_wait
    while True:
        resp = _post("DescribeTaskStatus", {"TaskId": task_id})
        data = resp["Data"]
        status = data["Status"]
        if status == 2:                       # 成功
            return data["Result"]
        if status in (3, -1):                 # 失败
            raise RuntimeError(f"识别任务失败: {data.get('ErrorMsg')}")
        if not poll or time.time() > deadline:
            raise RuntimeError("识别轮询超时未完成")
        time.sleep(3)


# ---------- 结果解析（文件识别 Result 是 JSON 字符串） ----------

def parse_result_to_segments(result_json: str) -> list:
    """把文件识别 Result 解析为带说话人标签的分段列表：[{speaker, text, start, end}]。

    兼容两种官方返回：
      - 词级别 JSON（ResTextFormat>=1）：{"Words":[{"Word","SpeakerId","StartTime","EndTime"}]}
      - 句子级文本（基础结果）："[起:止] 文本\n[起:止] 文本"
    """
    # 1) 词级别 JSON
    try:
        parsed = json.loads(result_json)
        words = parsed.get("Words") or []
        if words:
            segments = []
            cur = None
            for w in words:
                spk = f"说话人{w.get('SpeakerId', 0) + 1}"
                if cur is None or cur["speaker"] != spk:
                    cur = {"speaker": spk, "text": "", "start": w.get("StartTime", 0) / 1000.0,
                           "end": w.get("EndTime", 0) / 1000.0}
                    segments.append(cur)
                cur["text"] += w.get("Word", "")
                cur["end"] = w.get("EndTime", cur["end"]) / 1000.0
            return segments
        # 极少数情况下 JSON 内含纯文本字段
        text = parsed.get("Result") or parsed.get("Text") or ""
        if text:
            return _parse_sentence_lines(text)
        return []
    except (json.JSONDecodeError, TypeError):
        pass

    # 2) 句子级 "[起:止] 文本" 格式（基础结果 / 退化的字符串）
    return _parse_sentence_lines(str(result_json or ""))


def _parse_sentence_lines(text: str) -> list:
    """解析 `[mm:ss.mmm,mm:ss.mmm,说话人Id] 文本` 行，返回分段列表。

    腾讯云文件识别在开启说话人分离时，句子级结果形如：
        [0:0.070,0:4.760,0]  你好，欢迎参加今天的面试
    末尾的 `,说话人Id` 为可选项（基础结果无此字段）；需正确解析，
    否则时间戳与说话人标签都会丢失（退化为 0.0-0.0 / 说话人1）。
    """
    segs = []
    # 允许末尾可选的说话人 Id：\[起,止(,spkId)?\]
    pat = re.compile(r"\[(\d+):([\d.]+),(\d+):([\d.]+)(?:,(\d+))?\]\s*(.*)")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = pat.match(line)
        if m:
            sh, sm, eh, em, spk, txt = m.groups()
            start = int(sh) * 60 + float(sm)
            end = int(eh) * 60 + float(em)
            speaker = f"说话人{(int(spk) + 1) if spk is not None else 1}"
            if txt.strip():
                segs.append({"speaker": speaker, "text": txt.strip(),
                             "start": round(start, 3), "end": round(end, 3)})
        else:
            # 无时间戳的纯文本行
            segs.append({"speaker": "说话人1", "text": line, "start": 0.0, "end": 0.0})
    if segs:
        return segs
    # 整段无时间戳
    t = text.strip()
    return [{"speaker": "说话人1", "text": t, "start": 0.0, "end": 0.0}] if t else []


# ---------- 双流合并（实时单流 / 双文件分角色） ----------

def transcribe_single(audio_url: str, role: str, **kw) -> list:
    """单角色识别：提交任务→轮询→把整段标为同一角色。用于 HR / 候选人各自一路。"""
    task_id = create_recognition_task(audio_url, **kw)
    result = describe_task(task_id)
    result_str = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    segs = parse_result_to_segments(result_str)
    for s in segs:
        s["speaker"] = role
    return segs


def merge_streams(*role_segments: list) -> list:
    """把多路（每路已带 speaker 标签）按时间排序合并为一条 speakerTaggedTranscript。"""
    merged = []
    for segs in role_segments:
        merged.extend(segs)
    merged.sort(key=lambda s: s.get("start", 0))
    return merged


# ---------- 测试 / 离线用忠实 Mock（无腾讯凭证或音频未托管时） ----------

def simulate_recognition(role: str, text: str) -> list:
    """不联网的模拟识别：返回与给定文本一致的分段，用于本地流水线验证。
    role 标识说话人（HR / 候选人），与真实识别的产物结构一致。"""
    return [{"speaker": role, "text": text, "start": 0, "end": len(text), "mock": True}]


if __name__ == "__main__":
    # 自测：校验 CreateRecTask 请求体结构（不发网络）
    p = build_create_task_params("https://example.com/audio.mp3", voice_format=10)
    assert p["SpeakerDiarization"] == 1 and p["ResTextFormat"] == 1 and p["SourceType"] == 0
    print("build_create_task_params OK:", json.dumps(p, ensure_ascii=False))
    print("parse_result_to_segments sample:",
          parse_result_to_segments(json.dumps({"Words": [
              {"Word": "你", "SpeakerId": 0, "StartTime": 0, "EndTime": 200},
              {"Word": "好", "SpeakerId": 0, "StartTime": 200, "EndTime": 400},
              {"Word": "我", "SpeakerId": 1, "StartTime": 500, "EndTime": 700},
              {"Word": "可以", "SpeakerId": 1, "StartTime": 700, "EndTime": 900},
          ]})))
