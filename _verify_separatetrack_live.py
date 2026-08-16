"""
真实联调：TRTC 单流分轨录制 → 按轨道标说话人 → interviewEvaluation（不写飞书）
============================================================================
验证目标（用户要求）：
  1) 更稳的「TRTC 单流分轨录制 + 按轨道(UserID)标说话人」线上路径；
  2) 候选人身份 / 资格门禁：只有真实且资料完整的飞书候选人才能开视频房间。

做法：
  - edge-tts 生成 HR(女声) / 候选人(男声) 两段独立音频（各自单说话人）；
  - 用 TRTC 单流文件名规则（含 base64(UserId)）命名后上传真实 COS；
  - 验证 parse_userid_from_filename 反解轨道身份 + discover_recording_tracks 正确分轨；
  - 逐路真实文件识别(关闭 diarization) → 按轨道标 HR/候选人 → 合并 → 真实 DeepSeek 出 interviewEvaluation；
  - 门禁：用 TestClient 验证 /video/room 拒绝不存在的候选人（只读，不写飞书）。
全程 write_feishu=False，仅在验证末尾删除 COS 测试对象。
"""
from __future__ import annotations
import asyncio
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import edge_tts

from config import TRTC_APP_ID, COS_RECORD_PREFIX, COS_BUCKET
from src.trtc_recording import userid_to_filename_token, parse_userid_from_filename
from src import recording_pipeline
from src.cos_upload import get_cos_client

LOCAL = pathlib.Path("_verify_audio_sep")
LOCAL.mkdir(exist_ok=True)

HR_VOICE = "zh-CN-XiaoxiaoNeural"
CAND_VOICE = "zh-CN-YunxiNeural"
HR_TXT = "你好，欢迎来参加面试。请先做个自我介绍，然后说说你上一份工作做了多久、为什么离开。"
CAND_TXT = "你好，我叫李明，今年二十八岁。我之前在一家电子厂做了三年装配工，因为想回老家发展所以离职。"

ROOM_ID = 99000001
HR_USER = "hr_hr"
CAND_USER = "cand_rec_test_separate"
TEST_PREFIX = f"{COS_RECORD_PREFIX}{ROOM_ID}/testtask/"


async def tts(text: str, voice: str, out_path: str, tries: int = 3):
    last = None
    for i in range(tries):
        try:
            await edge_tts.Communicate(text, voice).save(out_path)
            if os.path.getsize(out_path) > 0:
                print(f"  [tts] {voice} -> {out_path} ({os.path.getsize(out_path)} bytes)")
                return
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"edge-tts 失败 {voice}: {last}")


def trtc_style_key(user_id: str, start_ms: int, end_ms: int) -> str:
    """构造模仿 TRTC 单流录制命名规则的文件名（含 base64(UserId)）。"""
    token = userid_to_filename_token(user_id)
    name = f"{TRTC_APP_ID}_{ROOM_ID}_{token}_s_audio_{start_ms}_{end_ms}.mp3"
    return TEST_PREFIX + name


def main():
    print("=== 1) 生成 HR / 候选人 独立音频（各自单说话人） ===")
    hr_mp3 = str(LOCAL / "hr.mp3")
    cand_mp3 = str(LOCAL / "cand.mp3")
    asyncio.run(tts(HR_TXT, HR_VOICE, hr_mp3))
    asyncio.run(tts(CAND_TXT, CAND_VOICE, cand_mp3))

    print("\n=== 2) 按 TRTC 单流命名规则上传真实 COS ===")
    hr_key = trtc_style_key(HR_USER, 0, 9000)
    cand_key = trtc_style_key(CAND_USER, 9000, 18000)
    client = get_cos_client()
    client.upload_file(Bucket=COS_BUCKET, Key=hr_key, LocalFilePath=hr_mp3)
    client.upload_file(Bucket=COS_BUCKET, Key=cand_key, LocalFilePath=cand_mp3)
    print(f"  HR  文件: {hr_key}")
    print(f"  候选人文件: {cand_key}")

    print("\n=== 3) 文件名→UserId 反解（单流分轨核心） ===")
    print(f"  HR  反解: {parse_userid_from_filename(hr_key)}  (期望 {HR_USER})")
    print(f"  候选人反解: {parse_userid_from_filename(cand_key)}  (期望 {CAND_USER})")
    assert parse_userid_from_filename(hr_key) == HR_USER
    assert parse_userid_from_filename(cand_key) == CAND_USER

    print("\n=== 4) discover_recording_tracks 自动按轨道分说话人 ===")
    tracks = recording_pipeline.discover_recording_tracks(
        ROOM_ID, hr_user_id=HR_USER, cand_user_id=CAND_USER)
    for t in tracks:
        print(f"  role={t['role']} user_id={t['user_id']} key=...{t['key'].split('/')[-1]}")
    roles = {t["role"] for t in tracks}
    assert roles == {"HR", "候选人"}, f"分轨失败: {roles}"

    print("\n=== 5) 逐路真实文件识别(关 diarization) → 按轨道标人 → 合并 → DeepSeek 评价 ===")
    out = recording_pipeline.process_recording(
        room_id=ROOM_ID, candidate="李明", job="装配工", family_key="firstline",
        candidate_id=CAND_USER, write_feishu=False,
        hr_user_id=HR_USER, candidate_user_id=CAND_USER, track_mode="separate")
    assert out["track_mode"] == "separate"
    seg_speakers = {s["speaker"] for s in out["segments"]}
    print(f"  合并后说话人集合: {seg_speakers}")
    assert seg_speakers == {"HR", "候选人"}, "说话人未按轨道正确标注"
    ev = out["evaluation"]
    print(f"  overallRating: {ev.get('overallRating')}")
    print(f"  dimensionScores: {[ (d.get('dim'), d.get('score')) for d in ev.get('dimensionScores', []) ]}")
    print(f"  hiringSuggestion: {ev.get('hiringSuggestion')}")
    print(f"  complianceFlags: {ev.get('complianceFlags')}")
    print(f"  纪要: {ev.get('transcriptSummary')[:120]}...")

    print("\n=== 6) 候选人资格门禁（只读，不写飞书） ===")
    from fastapi.testclient import TestClient
    from api.server import app
    c = TestClient(app)
    fake = c.post("/video/room", json={"candidate": "definitely_not_real_xyz"})
    print(f"  不存在候选人开房: success={fake.json().get('success')} eligible={fake.json().get('eligible')}")
    assert fake.json().get("success") is False and fake.json().get("eligible") is False
    # 真实 record_id 资格查询（取简历库中一条真实记录）
    from src.matcher_v2 import FeishuClient
    from config import RESUME_TABLE_ID
    real = FeishuClient().get_records(RESUME_TABLE_ID)[0]["record_id"]
    get_r = c.get(f"/video/candidate/{real}")
    print(f"  真实候选人查询: exists={get_r.json().get('exists')} name={get_r.json().get('name')}")

    print("\n=== 7) 清理 COS 测试对象 ===")
    for k in (hr_key, cand_key):
        try:
            client.delete_object(Bucket=COS_BUCKET, Key=k)
            print(f"  已删: {k}")
        except Exception as e:  # noqa: BLE001
            print(f"  删除失败 {k}: {e}")
    import shutil
    shutil.rmtree(LOCAL, ignore_errors=True)
    print("\n✅ 单流分轨录制 + 候选人门禁 全链路验证通过（未写飞书）。")


if __name__ == "__main__":
    main()
