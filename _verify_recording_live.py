"""
真实联调：TRTC 云端录制 → 文件识别(说话人分离) → interviewEvaluation
============================================================
因沙箱无法起真实 TRTC 房间，本脚本分两部分验证生产链路：

(A) 静态校验 TRTC 云端录制请求构造（build_start_params + TC3 签名结构）。
(B) 真实打通「录制文件 → 文件识别 → 评价」：
    edge-tts 模拟 HR/候选人「按句子交替发声」→ 用 ffmpeg 拼成单文件（带清晰说话人切换）
    → 上传真实 COS → 预签名回看链接 → 真实腾讯云文件识别(SourceType=0, 说话人分离)
    → 解析出 说话人1/说话人2 → interviewEvaluation。
    全程不写飞书（write_feishu=False），不污染真实数据。
"""
from __future__ import annotations
import asyncio
import json
import os
import re
import shutil
import tempfile

# 让腾讯云域名走直连（代理放行 DeepSeek/飞书，但不放行 asr/trtc/cos）
os.environ["NO_PROXY"] = ",".join([
    "asr.tencentcloudapi.com", "trtc.tencentcloudapi.com", "myqcloud.com", "*.myqcloud.com"
])
os.environ["no_proxy"] = os.environ["NO_PROXY"]

import edge_tts  # noqa: E402
import imageio_ffmpeg  # noqa: E402
from config import COS_BUCKET  # noqa: E402
from src import asr_file, recording_pipeline, trtc_recording  # noqa: E402
from src.cos_upload import get_cos_client, build_presigned_url  # noqa: E402
from src.interview_evaluation import generate_evaluation  # noqa: E402

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
ROOM = "test_room_live_001"
LOCAL = tempfile.mkdtemp(prefix="rec_verify_")


async def tts(text: str, voice: str, out_path: str):
    last = None
    for attempt in range(4):
        try:
            await edge_tts.Communicate(text, voice).save(out_path)
            print(f"  [tts] {voice} -> {out_path} ({os.path.getsize(out_path)} bytes)")
            return
        except Exception as e:  # noqa: BLE001
            last = e
            await asyncio.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"edge-tts 生成失败 {voice}: {last}")


def split_sentences(text: str) -> list:
    return [s.strip() for s in re.split(r"[。？！\.\?\!]", text) if s.strip()]


async def mix_interleaved(hr_sents: list, cand_sents: list, out_path: str):
    """把 HR/候选人句子交替生成短音频，再用 ffmpeg 拼成单文件（清晰说话人切换）。"""
    order = []
    i = j = 0
    while i < len(hr_sents) or j < len(cand_sents):
        if i < len(hr_sents):
            order.append(("hr", hr_sents[i], "zh-CN-XiaoxiaoNeural")); i += 1
        if j < len(cand_sents):
            order.append(("cand", cand_sents[j], "zh-CN-YunxiNeural")); j += 1
    paths = []
    for idx, (role, txt, voice) in enumerate(order):
        p = os.path.join(LOCAL, f"seg_{idx:02d}_{role}.mp3")
        await tts(txt + "。", voice, p)
        paths.append(p)
    list_txt = os.path.join(LOCAL, "list.txt")
    with open(list_txt, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(f"file '{p}'\n")
    r = subprocess_run(["-y", "-f", "concat", "-safe", "0", "-i", list_txt, "-c", "copy", out_path])
    if not (r == 0 and os.path.exists(out_path)):
        raise RuntimeError("ffmpeg 拼接失败")
    print(f"  [mix] ffmpeg 交替拼接 {len(paths)} 句 -> {out_path}")


def subprocess_run(args: list) -> int:
    import subprocess
    r = subprocess.run([FFMPEG, *args], capture_output=True, text=True)
    return r.returncode


async def main():
    print("=== (A) 静态校验 TRTC 云端录制请求构造 ===")
    p = trtc_recording.build_start_params(ROOM)
    assert p["RoomId"] == ROOM and p["RoomIdType"] == 0
    assert p["RecordParams"]["RecordMode"] in ("Audio", "Video", "VideoAndAudio")
    assert "CloudStorage" in p["StorageParams"]
    print("  build_start_params OK（RoomId/RoomIdType/RecordMode/COS 存储齐全）")
    auth = trtc_recording._tc3_sign("CreateCloudRecording", p)[0]
    assert auth.startswith("TC3-HMAC-SHA256 Credential=") and "Signature=" in auth
    print("  TC3 签名 OK（Authorization 头结构正确，含 Credential/Signature）")

    print("\n=== (B) 真实打通 录制文件 → 文件识别(说话人分离) → 评价 ===")
    hr_txt = "你好，欢迎参加今天的面试。请先做个自我介绍。我们这边是两班倒，你能接受吗？你上一份工作为什么离开？"
    cand_txt = "你好，我叫李明，今年28岁。之前在一家电子厂做了三年装配工。两班倒我可以接受，我以前也上过夜班。上一份工作是因为工厂搬迁我才离职的。"
    mixed = os.path.join(LOCAL, "mixed.mp3")
    await mix_interleaved(split_sentences(hr_txt), split_sentences(cand_txt), mixed)

    key = f"interview-records/{ROOM}/mixed.mp3"
    client = get_cos_client()
    client.put_object(Bucket=COS_BUCKET, Body=open(mixed, "rb").read(), Key=key, ContentType="audio/mpeg")
    print(f"  [cos] 已上传 {key} 到桶 {COS_BUCKET}")
    url = build_presigned_url(key, expired=7200)

    print("  [asr] 提交文件识别任务（SourceType=0, 说话人分离）...")
    segments = recording_pipeline.asr_recording_url(url, diarization=True)
    print(f"  [asr] 识别分段数={len(segments)}，说话人集合={sorted({s['speaker'] for s in segments})}")
    for s in segments:
        print(f"    - {s['speaker']} [{s['start']:.1f}-{s['end']:.1f}s]: {s['text']}")

    print("  [eval] DeepSeek 生成 interviewEvaluation ...")
    ev = generate_evaluation(segments, "firstline")
    print("    overallRating:", ev.get("overallRating"))
    for d in ev.get("dimensionScores", []):
        print(f"      {d.get('dim')}: {d.get('score')} ({d.get('state')})")
    print("    hiringSuggestion:", ev.get("hiringSuggestion"))
    print("    complianceFlags:", ev.get("complianceFlags"))

    client.delete_object(Bucket=COS_BUCKET, Key=key)
    print(f"\n[cleanup] 已删除 COS 测试对象 {key}")
    shutil.rmtree(LOCAL, ignore_errors=True)
    print(f"[cleanup] 已清理本地临时目录 {LOCAL}")
    print("\n=== 联调结论 ===")
    print("TRTC 录制请求构造/签名：OK（需真实房间才能实跑 CreateCloudRecording）")
    print("录制文件→ASR(SourceType=0,说话人分离)→interviewEvaluation：真实跑通 ✅")
    print("飞书写回：本验证未触发（write_feishu=False），生产用 /video/recording/process 默认写回。")


if __name__ == "__main__":
    asyncio.run(main())
