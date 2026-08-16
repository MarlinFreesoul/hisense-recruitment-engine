"""
视频面试 · 录制后处理流水线（生产链路）
====================================
把「TRTC 云端录制落盘的音频」变成「结构化面试评价并写回飞书」：

  discover_recording  (COS 列举最新录制文件 → 预签名回看链接)
        ↓
  asr_recording_url   (真实腾讯云文件识别，SourceType=0 + 说话人分离 → 带说话人标签的分段)
        ↓
  generate_evaluation (DeepSeek 产出 interviewEvaluation；合规本地检测)
        ↓
  （可选）写回飞书「面试记录」表

这是赛题模块 3「基于线上面试对话内容自动梳理面试纪要、打分评级」的生产落地：
实时阶段只用 HR 一路流式 ASR 做现场辅助，权威纪要/评分由这里的事后文件识别完成。
"""
from __future__ import annotations
import json

from config import COS_BUCKET, COS_RECORD_PREFIX, INTERVIEW_TABLE_ID
from src import asr_file
from src.cos_upload import build_presigned_url, get_cos_client
from src.interview_evaluation import generate_evaluation


# ---------- 1) 发现录制文件（COS） ----------

def discover_recording(room_id, candidate_id: str = None, prefix: str = None,
                       max_retry: int = 6, retry_wait: float = 5.0) -> dict:
    """在 COS 中查找该房间最新的录制文件，返回 {key, url, bucket, region}。

    录制刚结束文件可能延迟落盘，故带有限重试。url 为带时效的预签名回看链接（避免长期公开）。
    """
    import time
    client = get_cos_client()
    if prefix is None:
        # 优先按 candidate 维度，其次按 room
        prefix = f"{COS_RECORD_PREFIX}{candidate_id}/" if candidate_id else f"{COS_RECORD_PREFIX}{room_id}/"
    last_err = None
    for _ in range(max(1, max_retry)):
        try:
            resp = client.list_objects(Bucket=COS_BUCKET, Prefix=prefix)
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(retry_wait)
            continue
        contents = resp.get("Contents", []) or []
        if contents:
            latest = max(contents, key=lambda o: o.get("LastModified", ""))
            key = latest["Key"]
            return {
                "key": key,
                "url": build_presigned_url(key, expired=7200),
                "bucket": COS_BUCKET,
                "region": client._conf._region if hasattr(client, "_conf") else "",
            }
        time.sleep(retry_wait)
    raise RuntimeError(f"未在 COS 前缀 {prefix} 找到录制文件（已重试 {max_retry} 次）：{last_err}")


# ---------- 2) 真实文件识别（带说话人分离） ----------

def asr_recording_url(url: str, *, diarization: bool = True, engine: str = None) -> list:
    """对录制文件 URL 调腾讯云文件识别（SourceType=0），开启说话人分离。

    返回 parse_result_to_segments 解析后的带说话人标签分段：
    [{speaker:"说话人1"/"说话人2", text, start, end}, ...]
    """
    task_id = asr_file.create_recognition_task(
        url, engine_model_type=engine, speaker_diarization=diarization)
    result = asr_file.describe_task(task_id)
    result_str = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    return asr_file.parse_result_to_segments(result_str)


# ---------- 2b) 单流分轨：按轨道(UserID)识别并标说话人（更稳，无需 diarization） ----------

def discover_recording_tracks(room_id, hr_user_id: str = None, cand_user_id: str = None,
                              max_retry: int = 6, retry_wait: float = 5.0) -> list:
    """在 COS 中查找该房间所有录制文件，按文件名中的 UserId 映射说话人角色。

    返回 [{role:"HR"/"候选人", user_id, key, url, start_sec, end_sec}, ...]（仅含已知角色）。
    room_id 对应的单流文件位于 <COS_RECORD_PREFIX><room_id>/<TaskId>/... 下。
    """
    import time
    from src.trtc_recording import parse_userid_from_filename, parse_filename_timing
    client = get_cos_client()
    prefix = f"{COS_RECORD_PREFIX}{room_id}/"
    last_err = None
    for _ in range(max(1, max_retry)):
        try:
            resp = client.list_objects(Bucket=COS_BUCKET, Prefix=prefix)
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(retry_wait)
            continue
        contents = resp.get("Contents", []) or []
        if contents:
            tracks = []
            for o in contents:
                key = o["Key"]
                if key.lower().endswith((".m3u8", ".ts")):  # 跳过 HLS 索引/切片，只取封装音视频
                    continue
                uid = parse_userid_from_filename(key)
                if uid is None:
                    continue
                # 角色归属：优先精确匹配已知 userId，否则按前缀
                if cand_user_id and uid == cand_user_id:
                    role = "候选人"
                elif hr_user_id and uid == hr_user_id:
                    role = "HR"
                elif uid.startswith("cand_"):
                    role = "候选人"
                elif uid.startswith("hr_"):
                    role = "HR"
                else:
                    continue  # 录制机器人 / 未知轨道，跳过
                start_sec, end_sec = parse_filename_timing(key)
                tracks.append({
                    "role": role, "user_id": uid, "key": key,
                    "url": build_presigned_url(key, expired=7200),
                    "start_sec": start_sec, "end_sec": end_sec,
                })
            if tracks:
                return tracks
        time.sleep(retry_wait)
    raise RuntimeError(f"未在 COS 前缀 {prefix} 找到有效分轨录制文件（已重试 {max_retry} 次）：{last_err}")


def asr_track(url: str, *, engine: str = None) -> list:
    """对单条轨道音频（单一说话人）做文件识别，关闭说话人分离（已知身份，无需分离）。"""
    return asr_recording_url(url, diarization=False, engine=engine)


def _label_and_offset(tracks: list) -> list:
    """把分轨识别结果按角色标说话人，并用文件名全局时间做时间轴对齐/合并。"""
    merged = []
    for t in tracks:
        segs = t["segments"]
        role_label = "HR" if t["role"] == "HR" else "候选人"
        off = t.get("start_sec", 0.0) or 0.0
        for s in segs:
            merged.append({
                "speaker": role_label,
                "text": s.get("text", ""),
                "start": round((s.get("start", 0) or 0) + off, 3),
                "end": round((s.get("end", 0) or 0) + off, 3),
            })
    merged.sort(key=lambda x: x["start"])
    return merged


# ---------- 3) 统一处理：识别 → 评价 →（可选）写飞书 ----------

def build_feishu_fields(evaluation: dict, candidate: str, recording_url: str, job: str = "",
                        candidate_id: str = "") -> dict:
    """把 interviewEvaluation 结构化为飞书「面试记录」表字段（与 /video/report 保持一致）。

    candidate_id : 飞书简历库 record_id，作为唯一归属标识写入记录，确保不同候选人不混淆。
    """
    dims = evaluation.get("dimensionScores", []) if isinstance(evaluation, dict) else []
    dim_txt = "\n".join(
        f"- {d.get('dim')}：{d.get('score')}分（{d.get('state')}）{d.get('evidence', '')}"
        for d in dims)
    flags = evaluation.get("complianceFlags", []) if isinstance(evaluation, dict) else []
    summary = evaluation.get("transcriptSummary", "") if isinstance(evaluation, dict) else ""
    suggestion = evaluation.get("hiringSuggestion", "") if isinstance(evaluation, dict) else ""
    tagged = "\n".join(
        f"{s.get('speaker')}：{s.get('text')}" for s in evaluation.get("speakerTaggedTranscript", []))
    # 候选人唯一 ID 作为归属锚点，写入记录首行，避免不同候选人面试记录混淆
    id_line = f"[候选人ID: {candidate_id}]\n" if candidate_id else ""
    fields = {
        "候选人姓名": candidate or "",
        "面试阶段": "视频面试",
        "面试记录": (
            f"{id_line}"
            f"【综合评级】{evaluation.get('overallRating', '')} / 10\n"
            f"【维度分】\n{dim_txt}\n"
            f"【录用建议（AI辅助，不替决策）】{suggestion}\n"
            f"【合规预警】{('；'.join(flags) if flags else '无')}\n"
            f"【面试纪要】{summary}\n\n--- 双人转写 ---\n{tagged}"
        ),
    }
    if recording_url:
        fields["录制链接"] = recording_url
    if job:
        fields["应聘岗位"] = job
    return fields


def process_recording(room_id=None, recording_url: str = None, candidate: str = "",
                      job: str = "", family_key: str = "firstline",
                      candidate_id: str = None, write_feishu: bool = True,
                      hr_speaker: str = None,
                      hr_user_id: str = None, candidate_user_id: str = None,
                      track_mode: str = "auto") -> dict:
    """录制后处理主流程。

    track_mode:
      - "separate"：单流分轨（按轨道 UserId 标说话人，更稳，推荐线上用）；
      - "mixed"   ：合流单文件 + 说话人分离（线下混音录音等）；
      - "auto"    ：给了 hr/candidate_user_id 且未给单文件 URL 时自动走 separate，否则 mixed。
    优先用 recording_url（自动触发回调里已拿到文件地址）；否则按 room_id 到 COS 发现文件。
    candidate_id：飞书简历 record_id，写回飞书时作为唯一归属标识。
    返回 {track_mode, recording_url, segments, evaluation, feishu_ok, feishu_result}。
    """
    use_separate = (track_mode == "separate") or (
        track_mode == "auto" and hr_user_id and candidate_user_id and not recording_url)
    if use_separate:
        return process_recording_separate(
            room_id=room_id, candidate=candidate, job=job, family_key=family_key,
            candidate_id=candidate_id, write_feishu=write_feishu,
            hr_user_id=hr_user_id, candidate_user_id=candidate_user_id)

    if not recording_url:
        found = discover_recording(room_id, candidate_id=candidate_id)
        recording_url = found["url"]

    segments = asr_recording_url(recording_url, diarization=True)
    evaluation = generate_evaluation(segments, family_key, hr_speaker=hr_speaker)

    out = {
        "track_mode": "mixed",
        "recording_url": recording_url,
        "segments": segments,
        "evaluation": evaluation,
        "feishu_ok": None,
        "feishu_result": None,
    }

    if write_feishu:
        from src.matcher_v2 import FeishuClient
        fields = build_feishu_fields(evaluation, candidate, recording_url, job, candidate_id=candidate_id)
        result = FeishuClient().create_records(INTERVIEW_TABLE_ID, [fields])
        out["feishu_ok"] = result.get("code") == 0
        out["feishu_result"] = result

    return out


def process_recording_separate(room_id=None, candidate: str = "", job: str = "",
                               family_key: str = "firstline", candidate_id: str = None,
                               write_feishu: bool = True,
                               hr_user_id: str = None, candidate_user_id: str = None) -> dict:
    """单流分轨后处理：发现各分轨文件 → 逐路单说话人识别 → 按轨道标 HR/候选人 → 合并 → 评价。

    说话人身份来自轨道 UserId（HR / 候选人），不依赖说话人分离，更稳。
    """
    tracks_meta = discover_recording_tracks(room_id, hr_user_id=hr_user_id, cand_user_id=candidate_user_id)
    for t in tracks_meta:
        t["segments"] = asr_track(t["url"])
    merged = _label_and_offset(tracks_meta)
    # 分轨已知身份：HR 轨道即 HR，无需再靠 diarization 判定
    evaluation = generate_evaluation(merged, family_key, hr_speaker="HR")

    out = {
        "track_mode": "separate",
        "tracks": [{"role": t["role"], "user_id": t["user_id"], "key": t["key"]} for t in tracks_meta],
        "segments": merged,
        "evaluation": evaluation,
        "feishu_ok": None,
        "feishu_result": None,
    }

    if write_feishu:
        from src.matcher_v2 import FeishuClient
        # 录制回看链接取候选人轨（或第一条）
        rec_url = next((t.get("url") for t in tracks_meta if t["role"] == "候选人"),
                       tracks_meta[0]["url"] if tracks_meta else "")
        fields = build_feishu_fields(evaluation, candidate, rec_url, job, candidate_id=candidate_id)
        result = FeishuClient().create_records(INTERVIEW_TABLE_ID, [fields])
        out["feishu_ok"] = result.get("code") == 0
        out["feishu_result"] = result

    return out


if __name__ == "__main__":
    # 演示：给定一份录制文件 URL（需公网可访问）即可跑通整条链路
    import sys
    if len(sys.argv) < 3:
        print("用法: python -m src.recording_pipeline <recording_url> <candidate> [family_key]")
    else:
        url, cand = sys.argv[1], sys.argv[2]
        fam = sys.argv[3] if len(sys.argv) > 3 else "firstline"
        res = process_recording(recording_url=url, candidate=cand, family_key=fam, write_feishu=False)
        print(json.dumps(res["evaluation"], ensure_ascii=False, indent=2))
