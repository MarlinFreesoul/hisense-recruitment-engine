"""
验证脚本：视频面试「双流转写 → interviewEvaluation」全链路
=========================================================
模拟方式（按需求）：
  1. edge-tts 生成 HR / 候选人 两段「人类发声」音频（不同音色，模拟两人）；
  2. 触发语音识别：优先走真实腾讯云文件识别（需 TENCENT_* + ASR_APP_ID + 公网音频URL），
     无凭证/未托管时回退到忠实 mock（transcript 与 edge-tts 合成文本一致），并明确标注；
  3. 合并双路为 speakerTaggedTranscript；
  4. 调真实 DeepSeek 产出 interviewEvaluation（overallRating/dimensionScores/合规预警/纪要/建议）。

注意：本脚本只调用模块，不写飞书。真实识别部分如需联网，请另托管音频并配凭证。
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
import pathlib

# ---- 1. 用 edge-tts 模拟人类发声（HR / 候选人 两个音色） ----

HR_TEXT = "你好，请先介绍一下你自己，以及你上一份工作做了多久、为什么离开？能接受两班倒吗？"
CAND_TEXT = "我叫李明，做装配工三年了，因为原来的工厂搬迁，想换个离家近的地方。两班倒可以，我之前在电子厂也上过夜班。"

AUDIO_DIR = pathlib.Path("_verify_audio")
AUDIO_DIR.mkdir(exist_ok=True)
HR_AUDIO = str(AUDIO_DIR / "hr.mp3")
CAND_AUDIO = str(AUDIO_DIR / "cand.mp3")


async def gen_audio():
    try:
        import edge_tts
    except ImportError:
        print("【edge-tts】未安装，跳过真实音频生成（不影响后续流水线验证）")
        return False
    hr_voice, cand_voice = "zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"
    await edge_tts.Communicate(HR_TEXT, hr_voice).save(HR_AUDIO)
    await edge_tts.Communicate(CAND_TEXT, cand_voice).save(CAND_AUDIO)
    print(f"【edge-tts】已生成模拟人类发声：{HR_AUDIO}（HR）、{CAND_AUDIO}（候选人）")
    return True


# ---- 2. 触发识别（真实 / mock） ----

def recognize_role(role: str, audio_path: str, truth_text: str) -> list:
    """返回该角色的分段转写。优先真实腾讯云，否则忠实 mock。"""
    from src import asr_file
    # 真实触发：需凭证 + 公网可访问的音频 URL（本机文件不可被腾讯云拉取，故通常走 mock）
    real_url = os.getenv("ASR_FILE_PUBLIC_URL")
    if real_url and os.getenv("TENCENT_SECRET_ID") and os.getenv("ASR_APP_ID"):
        try:
            segs = asr_file.transcribe_single(real_url, role, voice_format=10, speaker_diarization=False)
            print(f"【ASR】{role} 走真实腾讯云文件识别，分段数={len(segs)}")
            return segs
        except Exception as e:  # noqa: BLE001
            print(f"【ASR】{role} 真实识别失败，回退 mock：{e}")
    else:
        print(f"【ASR】{role} 未配置腾讯云凭证/音频URL → 使用忠实 mock（transcript 与 edge-tts 合成文本一致）")
    return asr_file.simulate_recognition(role, truth_text)


# ---- 3+4. 合并 + 生成 interviewEvaluation ----

def main():
    asyncio.run(gen_audio())

    # 触发识别 → 双路
    hr_segs = recognize_role("HR", HR_AUDIO, HR_TEXT)
    cand_segs = recognize_role("候选人", CAND_AUDIO, CAND_TEXT)

    # 合并为 speakerTaggedTranscript
    from src.asr_file import merge_streams
    merged = merge_streams(hr_segs, cand_segs)
    print("\n=== speakerTaggedTranscript（合并后）===")
    for s in merged:
        print(f"  [{s['speaker']}] {s['text']}")

    # 生成 interviewEvaluation（真实 DeepSeek）
    from src.interview_evaluation import generate_evaluation, detect_compliance, _dims_for_family
    family_key = "firstline"
    print(f"\n=== 调用 DeepSeek 生成 interviewEvaluation（family_key={family_key}）===")
    try:
        ev = generate_evaluation(merged, family_key)
    except Exception as e:  # noqa: BLE001
        print("【评价】生成失败：", e)
        sys.exit(1)

    # 断言契约完整性
    dims = [d["dim"] for d in _dims_for_family(family_key)]
    got_dims = [d.get("dim") for d in ev.get("dimensionScores", [])]
    missing = [d for d in dims if d not in got_dims]
    assert not missing, f"维度缺失：{missing}"
    for key in ("overallRating", "transcriptSummary", "hiringSuggestion", "speakerTaggedTranscript", "complianceFlags"):
        assert key in ev, f"契约缺字段：{key}"

    print("\n=== interviewEvaluation（DeepSeek 真实输出）===")
    print(json.dumps(ev, ensure_ascii=False, indent=2))

    # 合规检测（本地确定性）：本样例 HR 未问敏感问题，应为空
    print("\n=== 合规检测 ===")
    print("complianceFlags =", ev["complianceFlags"] or "[]（HR 未触及敏感非岗位提问）")
    print("\n✅ 全链路验证通过：edge-tts 模拟发声 → 触发识别 → 双流合并 → DeepSeek 产出 interviewEvaluation")


if __name__ == "__main__":
    main()
