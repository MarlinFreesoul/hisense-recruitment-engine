"""
真实联调：视频面试「双流转写 → interviewEvaluation」
==================================================
前提：.env 已填好 TENCENT_SECRET_ID / TENCENT_SECRET_KEY（文件识别由凭证推导 APPID，无需公网托管）。
流程：
  1. edge-tts 生成 HR / 候选人 两段中文「人类发声」音频（不同音色）；
  2. 走真实腾讯云录音文件识别（SourceType=1，音频 base64 直传，<5MB）→ 得到真实转写；
  3. 按角色标注 + 合并为 speakerTaggedTranscript；
  4. 调真实 DeepSeek 产出 interviewEvaluation。
不写飞书（只调模块）。
"""
from __future__ import annotations
import asyncio
import json
import os
import pathlib

# 环境设了 HTTPS_PROXY，但代理不放行 asr.tencentcloudapi.com（握手超时）。
# 仅对该腾讯云域名走直连（绕过代理），其余仍走代理（DeepSeek/飞书保持原路径）。
os.environ["NO_PROXY"] = "asr.tencentcloudapi.com"
os.environ["no_proxy"] = "asr.tencentcloudapi.com"

import edge_tts

HR_TEXT = ("你好，欢迎来参加面试。请先简单介绍一下你自己，以及你上一份工作做了多久，"
           "为什么离开上一家公司？另外，我们这边是两班倒，你能接受吗？")
CAND_TEXT = ("你好，我叫李明，今年二十八岁。我之前在一家电子厂做了三年装配工，"
             "因为工厂搬迁到外地，所以想换一份离家近的工作。两班倒我可以接受，我以前也上过夜班。")

AUDIO_DIR = pathlib.Path("_verify_audio_live")
AUDIO_DIR.mkdir(exist_ok=True)
HR_AUDIO = str(AUDIO_DIR / "hr.mp3")
CAND_AUDIO = str(AUDIO_DIR / "cand.mp3")


async def gen_audio():
    await edge_tts.Communicate(HR_TEXT, "zh-CN-XiaoxiaoNeural").save(HR_AUDIO)
    await edge_tts.Communicate(CAND_TEXT, "zh-CN-YunxiNeural").save(CAND_AUDIO)
    print(f"【edge-tts】已生成 HR 音频：{HR_AUDIO}")
    print(f"【edge-tts】已生成候选人音频：{CAND_AUDIO}")


def main():
    asyncio.run(gen_audio())

    from src import asr_file
    from src.interview_evaluation import generate_evaluation, _dims_for_family

    # 2) 真实腾讯云文件识别（SourceType=1，音频直传）
    print("\n=== 真实识别：HR 音频 ===")
    hr_bytes = pathlib.Path(HR_AUDIO).read_bytes()
    hr_segs = asr_file.recognize_bytes(hr_bytes, "HR", voice_format=10)
    print("HR 真实转写：", " ".join(s["text"] for s in hr_segs))

    print("\n=== 真实识别：候选人音频 ===")
    cand_bytes = pathlib.Path(CAND_AUDIO).read_bytes()
    cand_segs = asr_file.recognize_bytes(cand_bytes, "候选人", voice_format=10)
    print("候选人真实转写：", " ".join(s["text"] for s in cand_segs))

    # 3) 合并：两份独立音频都从 0 开始，把候选人时间轴按 HR 时长偏移，得到顺序对话
    hr_end = max((s["end"] for s in hr_segs), default=0.0)
    for s in cand_segs:
        s["start"] += hr_end
        s["end"] += hr_end
    merged = asr_file.merge_streams(hr_segs, cand_segs)
    print("\n=== speakerTaggedTranscript（合并后）===")
    for s in merged:
        print(f"  [{s['speaker']}] {s['text']}")

    # 4) 真实 DeepSeek 产出 interviewEvaluation
    family_key = "firstline"
    print(f"\n=== 真实 DeepSeek 生成 interviewEvaluation（family_key={family_key}）===")
    ev = generate_evaluation(merged, family_key)
    dims = [d["dim"] for d in _dims_for_family(family_key)]
    got = [d.get("dim") for d in ev.get("dimensionScores", [])]
    assert not [d for d in dims if d not in got], "维度缺失"
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    print("\n✅ 真实联调跑通：edge-tts 模拟发声 → 腾讯云文件识别(真实) → 双流合并 → DeepSeek(真实) → interviewEvaluation")


if __name__ == "__main__":
    try:
        main()
    finally:
        import shutil
        shutil.rmtree(AUDIO_DIR, ignore_errors=True)
        print(f"（已清理临时音频目录 {AUDIO_DIR}）")
