"""
API 服务（FastAPI）
==================
同事 / 前端通过 HTTP 调用后端能力，不用碰内部代码。

启动：uvicorn api.server:app --host 0.0.0.0 --port 8000
同事访问：http://<你的IP>:8000/docs （自动生成的接口文档）
"""
from __future__ import annotations
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.llm_resume_parser import parse_resume_with_llm, llm_result_to_feishu_fields
from src.matcher_v2 import run_matching
from src.interview_collect import generate_core_questions
from src.video_room import create_room
from src.realtime_asr import build_asr_connect_url
from src.interview_assist import suggest_assist
from src.interview_evaluation import generate_evaluation
from src.trtc_recording import start_recording, stop_recording, describe_recording, build_start_params
from src import recording_pipeline
from src.candidate import is_eligible, fetch_profile, register_profile, candidate_user_id
from src.screening import screen_resume
from src.talent_pool import get_pool
from src.jd_generator import generate_jd, load_family

app = FastAPI(title="海信 AI 招聘智能体 API", version="1.1", description="简历解析 + 人岗匹配评分 + 视频面试辅助")

# 允许前端（vinext / 静态 H5）跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResumeText(BaseModel):
    text: str


class ResumeImport(BaseModel):
    text: str
    job: str = ""  # 应聘岗位（评分绑定用）


class InterviewSummarize(BaseModel):
    candidate: str = ""
    job: str = ""
    conversation: str = ""


class InterviewSubmit(BaseModel):
    candidate: str = ""
    job: str = ""
    answers: dict = {}


class VideoRoomReq(BaseModel):
    candidate: str = ""          # 候选人标识（必须 = 飞书简历库 record_id）
    interviewer: str = "hr"      # 面试官标识（工号等）
    room_id: int = None          # 可选，指定固定房间号


class VideoCandidateRegisterReq(BaseModel):
    """候选人填写 / 修改资料。fields 为飞书简历库字段（姓名/最近职位/最近公司/工作年限…）。

    record_id 为空 → 新建一条简历记录（系统分配唯一 ID）；非空 → 更新该记录（保留同一 ID）。
    """
    record_id: str = ""
    fields: dict = {}


class VideoAssistReq(BaseModel):
    transcript: str = ""         # 当前面试转写文本（建议只传最近若干轮）
    family_key: str = "firstline"
    risk_points: list = []
    last_question: str = ""


class VideoReportReq(BaseModel):
    candidate: str = ""
    job: str = ""
    candidate_id: str = ""          # 飞书简历 record_id（唯一归属标识，避免候选人混淆）
    family_key: str = "firstline"   # 岗位族 key（用于 interviewEvaluation 维度）
    transcript: str = ""            # 旧：纯文本转写（向后兼容）
    speaker_transcript: list = []   # 新：带说话人标签的双人转写（推荐，来自 asr_file）
    recording_url: str = ""         # COS/回看链接（可选）


class VideoRecordingStartReq(BaseModel):
    room_id: int = None             # TRTC 房间号（与 /video/room 一致）
    candidate: str = ""             # 仅用于 COS 文件前缀归类
    bot_user: str = ""              # 录制机器人用户标识（默认取配置）


class VideoRecordingStopReq(BaseModel):
    task_id: str = ""               # start 返回的 task_id


class VideoRecordingProcessReq(BaseModel):
    room_id: int = None             # 按房间到 COS 发现最新录制
    candidate: str = ""
    job: str = ""
    family_key: str = "firstline"
    candidate_id: str = ""          # 飞书简历 record_id（唯一归属标识）
    recording_url: str = ""         # 也可直接给录制文件地址（自动触发回调场景）
    write_feishu: bool = True       # 是否结构化写回飞书「面试记录」表
    hr_speaker: str = ""            # 可选：指明哪一路是 HR（混合模式用）
    hr_user_id: str = ""            # 单流分轨：HR 的 TRTC userId（如 hr_hr）
    candidate_user_id: str = ""     # 单流分轨：候选人的 TRTC userId（如 cand_recxxx）
    track_mode: str = "auto"        # auto / separate / mixed


# ===================== 模块 1 + 模块 4：上传即打分 + 人才储备池 =====================

class ScreenReq(BaseModel):
    text: str = ""                  # 简历原文（优先 LLM 解析，无 key 走离线兜底）
    resume: dict = {}               # 或传结构化飞书字段风格 dict（与 text 二选一）
    job_family: str = ""            # 岗位族 key（firstline/process-equipment/...）；不传则按 job_name 推断
    job_name: str = ""              # 岗位名（用于推断岗位族 + 展示）
    intake: bool = True             # 是否自动入人才池（默认 True）
    write_feishu: bool = True       # 是否 best-effort 写回飞书（默认 True）


class OfferFallbackReq(BaseModel):
    job_family: str = ""            # 岗位族 key；不传则全池
    rejected_id: str = ""           # 放弃 Offer 的候选人 candidate_id；不传则取该岗位族当前排名第一
    hr_user_id: str = ""            # 单流分轨：HR 的 TRTC userId（如 hr_hr）
    candidate_user_id: str = ""     # 单流分轨：候选人的 TRTC userId（如 cand_recxxx）
    track_mode: str = "auto"        # auto / separate / mixed


class JdGenerateReq(BaseModel):
    """JD 生成请求：岗位族 + 可变参数（HR/用人部门可改）。"""
    job_family: str = "firstline"   # 岗位族 key
    params: dict = {}               # position / location / salary / extra_hard / extra_skills / soft_qualities ...


class DepartmentDecisionReq(BaseModel):
    """用人部门复核：对候选人筛选结论「通过 / 不通过」并填备注 → 推送 HR 电话初面。"""
    candidate_id: str = ""          # 候选人 id（人才池 / 评分结果里的标识）
    name: str = ""                  # 候选人姓名（便于展示与推送）
    job_family: str = ""            # 岗位族（决定同岗位族对比/递补上下文）
    decision: str = "通过"          # "通过" / "不通过"
    note: str = ""                  # 用人部门备注


class DepartmentPushReq(BaseModel):
    """HR 将已初筛候选人推送给用人部门复核（双向回环起点）。"""
    candidate_id: str = ""
    name: str = ""
    job_family: str = ""


# 用人部门复核记录（内存，演示不依赖飞书；若配群机器人则同步推送 HR）
DEPARTMENT_DECISIONS: list[dict] = []


@app.get("/health")
def health():
    return {"status": "ok", "service": "海信 AI 招聘智能体"}


@app.post("/parse_resume")
def parse_resume(req: ResumeText):
    """简历文本 → 结构化字段（LLM 解析，适配非标简历）。"""
    parsed = parse_resume_with_llm(req.text)
    return {"parsed": parsed, "feishu_fields": llm_result_to_feishu_fields(parsed)}


@app.post("/import_resume")
def import_resume(req: ResumeImport):
    """真实简历导入闭环：LLM 解析 → 写飞书简历库 → 自动评分 → 返回结构化 + 评分。"""
    from src.matcher_v2 import FeishuClient, feishu_to_resume, match_job_family, score_feishu_resume
    from src.jd_generator import load_family
    from config import RESUME_TABLE_ID

    parsed = parse_resume_with_llm(req.text)
    fields = llm_result_to_feishu_fields(parsed)
    fields["应聘岗位"] = req.job

    feishu = FeishuClient()
    r = feishu.create_records(RESUME_TABLE_ID, [fields])

    score = None
    family_key = match_job_family(req.job)
    if family_key:
        family = load_family(family_key)
        resume = feishu_to_resume(fields)
        score = score_feishu_resume(resume, family)

    return {
        "parsed": parsed,
        "feishu_fields": fields,
        "feishu_code": r.get("code"),
        "score": score,
    }


@app.post("/summarize_interview")
def summarize_interview_endpoint(req: InterviewSummarize):
    """线上面试对话 → 自动梳理面试纪要 + 评分评级。"""
    from src.interview import summarize_interview
    return summarize_interview(req.candidate, req.job, req.conversation)


@app.post("/match")
def match():
    """读飞书「招聘需求表 + 简历库」→ 评分 → 写回「评分结果表」。"""
    result = run_matching(write_back=True)
    return result


@app.get("/jobs")
def jobs():
    """读飞书招聘需求表所有岗位。"""
    from src.matcher_v2 import FeishuClient
    from config import JD_TABLE_ID
    records = FeishuClient().get_records(JD_TABLE_ID)
    return {"count": len(records), "jobs": [r["fields"] for r in records]}


@app.get("/resumes")
def resumes():
    """读飞书简历库所有简历。"""
    from src.matcher_v2 import FeishuClient
    from config import RESUME_TABLE_ID
    records = FeishuClient().get_records(RESUME_TABLE_ID)
    return {"count": len(records), "resumes": [r["fields"] for r in records]}


@app.get("/results")
def results():
    """读飞书评分结果表。"""
    from src.matcher_v2 import FeishuClient
    from config import RESULT_TABLE_ID
    records = FeishuClient().get_records(RESULT_TABLE_ID)
    return {"count": len(records), "results": [r["fields"] for r in records]}


@app.get("/interview/questions")
def interview_questions(candidate: str = "", assessment: str = ""):
    """读简历 + 风险点（+ 可选测评报告）→ 生成核心采集问题（参数化）。

    assessment：HR/系统录入的候选人测评报告文本，用于针对短板/测评结论定制个性化追问（PRD 模块 3）。
    """
    from src.matcher_v2 import FeishuClient, feishu_to_resume, match_job_family
    from src.risk_filter import risk_report
    from src.jd_generator import load_family
    from config import RESUME_TABLE_ID
    feishu = FeishuClient()
    records = feishu.get_records(RESUME_TABLE_ID)
    rec = next((r for r in records if r["record_id"] == candidate or r["fields"].get("姓名") == candidate), None)
    if not rec:
        return {"error": "未找到候选人，请传 candidate=record_id 或姓名"}
    resume = feishu_to_resume(rec["fields"])
    family_key = match_job_family(rec["fields"].get("最近职位", "")) or "firstline"
    family = load_family(family_key)
    risk = risk_report(resume, family)
    risk_points = [r for r in risk["risks"] if r["level"] != "低"]
    questions = generate_core_questions(family_key, resume, risk_points,
                                        assessment_report=assessment or None)
    return {"candidate": resume["name"], "job": rec["fields"].get("最近职位", ""),
            "family_key": family_key, "questions": questions}


@app.post("/interview/submit")
def interview_submit(req: InterviewSubmit):
    """接收回复 → 写飞书「面试采集表」。"""
    import json as _json
    from src.matcher_v2 import FeishuClient
    from config import INTERVIEW_COLLECT_TABLE_ID
    fields = {
        "候选人姓名": req.candidate or "",
        "应聘岗位": req.job or "",
        "采集内容": _json.dumps(req.answers, ensure_ascii=False),
    }
    result = FeishuClient().create_records(INTERVIEW_COLLECT_TABLE_ID, [fields])
    return {"success": result.get("code") == 0, "result": result}


@app.get("/demo_data")
def demo_data():
    """陈老师 demo 聚合数据：飞书真实 JD + 简历 + 评分 → demo 格式。"""
    from src.demo_data import build_demo_data
    return build_demo_data()


# ===================== 视频面试辅助（独立 TRTC + 独立 ASR） =====================

@app.post("/video/room")
def video_room(req: VideoRoomReq):
    """为「候选人 + 面试官」创建 TRTC 视频房间，返回双方 UserSig 与房间号。

    门禁（关键护栏）：候选人必须是飞书简历库中的真实记录，且必填资料已填写完整，
    否则拒绝创建房间——保证「每次视频对话都是真实候选人填完资料后才可以跟 HR 面试」。
    后端只签发 UserSig，音视频流由前端 TRTC Web SDK 直连腾讯云，不经本服务器。
    """
    # 1) 资格门禁：真实候选人 + 资料完整
    elig = is_eligible(req.candidate)
    if not elig["eligible"]:
        return {
            "success": False,
            "eligible": False,
            "reason": elig["reason"],
            "missing": elig.get("missing", []),
            "error": "候选人未通过面试资格校验，无法创建视频房间",
        }

    try:
        room = create_room(req.candidate, req.interviewer, req.room_id)
    except RuntimeError as e:
        return {"success": False, "eligible": True, "error": str(e)}

    # 透出候选人唯一 ID，前端/下游据此隔离，杜绝混淆
    room["candidate_id"] = req.candidate
    room["eligible"] = True
    return {"success": True, **room}


# ---------- 候选人身份与资格门禁 ----------

@app.get("/video/candidate/{candidate_id}")
def video_candidate_get(candidate_id: str):
    """查询某候选人的真实档案与面试资格（只读，安全）。"""
    prof = fetch_profile(candidate_id)
    if not prof:
        return {"success": False, "exists": False,
                "reason": "候选人不存在，或不是飞书简历库中的真实记录"}
    elig = is_eligible(candidate_id)
    return {
        "success": True,
        "exists": True,
        "candidate_id": candidate_id,
        "name": (prof.get("fields") or {}).get("姓名", ""),
        "eligible": elig["eligible"],
        "reason": elig["reason"],
        "missing": elig.get("missing", []),
    }


@app.post("/video/candidate/register")
def video_candidate_register(req: VideoCandidateRegisterReq):
    """候选人填写 / 修改资料，返回唯一候选人 ID 与资格状态。

    这是「先填资料、后面试」的入口：资料完整后该 ID 才具备视频面试资格。
    """
    try:
        res = register_profile(req.fields, req.record_id or None)
    except Exception as e:  # noqa: BLE001
        return {"success": False, "error": str(e)}
    return {
        "success": bool(res.get("record_id")),
        "candidate_id": res.get("record_id"),
        "eligible": res.get("eligible"),
        "missing": res.get("missing", []),
        "reason": res.get("reason"),
    }


@app.get("/video/asr")
def video_asr(voice_id: str = ""):
    """签出腾讯云实时语音识别的 WebSocket 连接串，供前端直接连（SecretKey 不下发浏览器）。

    前端拿 url 建 WebSocket，逐片推 PCM 音频，收 JSON 转写结果。
    """
    try:
        out = build_asr_connect_url(voice_id or None)
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, **out}


@app.post("/video/assist")
def video_assist(req: VideoAssistReq):
    """基于面试实时转写，调用 DeepSeek 给面试官返回追问建议 / 风险预警 / STAR 提示。"""
    try:
        assist = suggest_assist(req.transcript, req.family_key, req.risk_points, req.last_question)
    except (ValueError, Exception) as e:  # noqa: BLE001 - 把 LLM/网络错误透传给前端
        return {"success": False, "error": str(e)}
    return {"success": True, "assist": assist}


@app.post("/video/report")
def video_report(req: VideoReportReq):
    """生成视频面试结构化评价（interviewEvaluation）并写回飞书「面试记录」表。

    优先使用带说话人标签的双人转写（speaker_transcript，来自 asr_file 文件识别）；
    未提供时回退到纯文本转写。评价由 DeepSeek 基于转写生成；AI 仅辅助，
    不自动录用/淘汰（延续项目护栏）。complianceFlags 本地确定性检测 HR 敏感提问。
    """
    import json as _json
    from src.matcher_v2 import FeishuClient
    from config import INTERVIEW_TABLE_ID

    # 1) 生成面试评价（interviewEvaluation 契约）
    evaluation = None
    feishu_fields = {
        "候选人姓名": req.candidate or "",
        "面试阶段": "视频面试",
    }
    if req.recording_url:
        feishu_fields["录制链接"] = req.recording_url

    if req.speaker_transcript:
        try:
            evaluation = generate_evaluation(req.speaker_transcript, req.family_key)
        except Exception as e:  # noqa: BLE001
            evaluation = {"error": f"评价生成失败：{e}"}
        # 结构化写回飞书：评分概览 + 合规标记 + 纪要 + 原始双人转写
        dims = evaluation.get("dimensionScores", []) if isinstance(evaluation, dict) else []
        dim_txt = "\n".join(f"- {d.get('dim')}：{d.get('score')}分（{d.get('state')}）{d.get('evidence','')}"
                            for d in dims)
        flags = evaluation.get("complianceFlags", []) if isinstance(evaluation, dict) else []
        summary = evaluation.get("transcriptSummary", "") if isinstance(evaluation, dict) else ""
        suggestion = evaluation.get("hiringSuggestion", "") if isinstance(evaluation, dict) else ""
        tagged = "\n".join(f"{s.get('speaker')}：{s.get('text')}" for s in req.speaker_transcript)
        feishu_fields["面试记录"] = (
            f"【综合评级】{evaluation.get('overallRating','')} / 10\n"
            f"【维度分】\n{dim_txt}\n"
            f"【录用建议（AI辅助，不替决策）】{suggestion}\n"
            f"【合规预警】{('；'.join(flags) if flags else '无')}\n"
            f"【面试纪要】{summary}\n\n--- 双人转写 ---\n{tagged}"
        )
    else:
        # 向后兼容：纯文本转写
        from src.interview_assist import suggest_assist
        summary_prompt_transcript = (req.transcript or "")[:4000]
        try:
            assist = suggest_assist(summary_prompt_transcript, req.family_key, [], "")
            eval_text = (
                f"【建议追问】{assist.get('建议追问', '')}\n"
                f"【风险预警】{assist.get('风险预警', '')}\n"
                f"【STAR提示】{assist.get('STAR提示', '')}"
            )
        except Exception as e:  # noqa: BLE001
            eval_text = f"（评价生成失败：{e}）\n原始转写：\n{summary_prompt_transcript}"
        feishu_fields["面试记录"] = f"{eval_text}\n\n--- 转写原文 ---\n{req.transcript or ''}"

    # 2) 写回飞书「面试记录」表（候选人唯一 ID 作为归属锚点，避免不同候选人混淆）
    if req.candidate_id and feishu_fields.get("面试记录"):
        feishu_fields["面试记录"] = f"[候选人ID: {req.candidate_id}]\n" + feishu_fields["面试记录"]
    try:
        result = FeishuClient().create_records(INTERVIEW_TABLE_ID, [feishu_fields])
        feishu_ok = result.get("code") == 0
    except Exception as e:  # noqa: BLE001
        result, feishu_ok = {"error": str(e)}, False

    return {
        "success": feishu_ok,
        "evaluation": evaluation,
        "feishu_result": result,
    }


# ---------- TRTC 云端录制控制 + 自动触发文件识别 → 写飞书 ----------

@app.post("/video/recording/start")
def video_recording_start(req: VideoRecordingStartReq):
    """启动 TRTC 云端录制（一个服务端机器人进房录制），返回 task_id。

    面试开始时调用；结束后调 /video/recording/stop，录制文件落 COS。
    真正读取 TRTC_RECORD_ENABLED 开关：未开启则拒绝启动，避免无谓请求。
    """
    from config import TRTC_RECORD_ENABLED
    if not TRTC_RECORD_ENABLED:
        return {"success": False,
                "error": "云端录制未启用（TRTC_RECORD_ENABLED=false），请先在配置中开启后再启动"}
    try:
        rec = start_recording(req.room_id, req.bot_user or None)
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, **rec}


@app.post("/video/recording/stop")
def video_recording_stop(req: VideoRecordingStopReq):
    """停止云端录制（DeleteCloudRecording）。"""
    try:
        resp = stop_recording(req.task_id)
    except (RuntimeError, ValueError) as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "response": resp}


@app.post("/video/recording/process")
def video_recording_process(req: VideoRecordingProcessReq):
    """录制后处理：发现/接收录制文件 → 文件识别 → interviewEvaluation →（可选）写飞书。

    track_mode=separate：单流分轨（按轨道 UserId 标说话人，更稳，线上推荐）；
    自动触发场景：/video/recording/callback 在录制完成后调用本流程。
    """
    try:
        out = recording_pipeline.process_recording(
            room_id=req.room_id, recording_url=req.recording_url,
            candidate=req.candidate, job=req.job, family_key=req.family_key,
            candidate_id=req.candidate_id or None, write_feishu=req.write_feishu,
            hr_speaker=req.hr_speaker or None,
            hr_user_id=req.hr_user_id or None, candidate_user_id=req.candidate_user_id or None,
            track_mode=req.track_mode or "auto")
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, **out}


@app.post("/video/recording/callback")
async def video_recording_callback(body: dict = None):
    """腾讯云录制完成回调（自动触发文件识别 → 评价 → 写飞书）。

    真实回调体含 EventInfo.RecordFileList[].FileUrl 等；这里做尽力解析：
    优先取 file_url / RecordFileList，其次 room_id，再触发 process。
    若配置了 VIDEO_CALLBACK_TOKEN，需校验回调签名（此处为占位校验点）。
    """
    try:
        payload = body or {}
        # 1) 可选：回调鉴权（腾讯云录制回调可带签名，此处留校验点）
        from config import VIDEO_CALLBACK_TOKEN
        if VIDEO_CALLBACK_TOKEN and payload.get("sign") != VIDEO_CALLBACK_TOKEN:
            return {"success": False, "error": "callback sign mismatch"}

        # 2) 尽力提取文件地址与房间号
        recording_url = ""
        room_id = None
        evt = payload.get("EventInfo", payload)
        file_list = evt.get("RecordFileList") or evt.get("record_file_list") or []
        if isinstance(file_list, list) and file_list:
            recording_url = file_list[0].get("FileUrl") or file_list[0].get("file_url") or ""
        recording_url = recording_url or payload.get("file_url") or payload.get("FileUrl") or ""
        room_id = payload.get("room_id") or evt.get("RoomId") or payload.get("RoomId")

        cand = str(payload.get("candidate", ""))
        # 单流分轨：从候选人 record_id 推导其 TRTC userId，HR 默认 hr_hr
        cand_uid = payload.get("candidate_user_id") or (f"cand_{cand}" if cand else None)
        hr_uid = payload.get("hr_user_id") or "hr_hr"
        family_key = str(payload.get("family_key", "firstline"))

        if room_id is not None:
            # 单流分轨：按房间到 COS 发现各分轨文件（HR/候选人），按轨道标说话人
            out = recording_pipeline.process_recording(
                room_id=room_id, candidate=cand, family_key=family_key,
                candidate_id=cand or None, write_feishu=True,
                hr_user_id=hr_uid, candidate_user_id=cand_uid, track_mode="separate")
        else:
            # 兜底：仅拿到单个文件 URL（合流/旧格式），走混合+说话人分离
            out = recording_pipeline.process_recording(
                recording_url=recording_url, candidate=cand, family_key=family_key,
                candidate_id=cand or None, write_feishu=True,
                hr_speaker=payload.get("hr_speaker") or None, track_mode="mixed")
        return {"success": True, "accepted": True, **out}
    except Exception as e:  # noqa: BLE001
        return {"success": False, "error": str(e)}


# ---------- 模块 1：上传即打分（不依赖飞书即可跑通主干） ----------

@app.post("/screen")
def screen(req: ScreenReq):
    """上传简历即打分 + 自动入人才池。

    - text：简历原文（有 DeepSeek key 走 LLM 解析，否则离线正则兜底）
    - resume：结构化飞书字段风格 dict（与 text 二选一）
    - job_family / job_name：指定岗位（决定用哪套岗位族权重）
    返回确定性三态评分契约 + 人才池入池结果（候选人在池中的 id）。
    """
    try:
        out = screen_resume(
            text=req.text, resume=req.resume or None,
            job_family=req.job_family or None, job_name=req.job_name or None,
            intake=req.intake, write_feishu=req.write_feishu)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"success": False, "error": f"打分失败：{e}"}
    return {"success": True, **out}


# ---------- 模块 1：真实简历文件上传即打分（替换前端假 toast） ----------
def _extract_resume_text(filename: str, raw: bytes) -> str:
    """从上传的简历文件抽取纯文本：pdf 走 PyMuPDF；其余按文本解码（离线兜底）。"""
    ext = (filename or "").lower()
    if ext.endswith(".pdf"):
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        try:
            tmp.write(raw)
            tmp.close()
            from src.resume_parser import extract_text_from_pdf
            txt = extract_text_from_pdf(tmp.name)
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
        return txt or raw.decode("utf-8", "ignore")
    # .txt / .md / .docx(无 python-docx 时当作纯文本) 统一按文本解码
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", "ignore")


@app.post("/screen/upload")
async def screen_upload(file: UploadFile = File(...),
                        job_family: str = Form(""),
                        job_name: str = Form(""),
                        write_feishu: bool = Form(True)):
    """真实简历文件上传即打分 + 自动入人才池。

    - 支持 PDF / TXT / MD（Word 无 python-docx 时按纯文本兜底）。
    - 抽取文本后复用 /screen 的确定性三态引擎（有 DeepSeek key 走 LLM 解析，否则离线正则兜底）。
    - 合格候选自动入内存人才池（配置 TALENT_POOL_TABLE_ID 时 best-effort 写回飞书）。
    让前端「新投递简历 → 投递即筛选」在演示层真正跑通（替代原假 toast）。
    """
    raw = await file.read()
    text = _extract_resume_text(file.filename or "", raw)
    if not text.strip():
        return {"success": False, "error": "未能从文件中解析出简历文本"}
    try:
        out = screen_resume(
            text=text,
            job_family=job_family or None,
            job_name=job_name or None,
            intake=True,
            write_feishu=write_feishu)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"success": False, "error": f"打分失败：{e}"}
    return {"success": True, "filename": file.filename, **out}


# ---------- 模块 4：人才储备池对比表 + Offer 放弃秒级递补 ----------

@app.get("/talent-pool")
def talent_pool(job_family: str = ""):
    """同岗位族（或全池）候选人对比表（PRD 模块 4 comparisonMatrix）。"""
    pool = get_pool()
    rows = pool.comparison_matrix(job_family or None)
    return {"count": len(rows), "job_family": job_family or "全部", "comparison": rows}


@app.post("/decision/offer-fallback")
def offer_fallback(req: OfferFallbackReq):
    """Offer 放弃秒级递补：标记放弃者 → 同岗位族按匹配度顺位推举下一合适候选人。

    自动写回飞书「人才储备池」表状态，并通过群机器人推送递补汇总（若已配置）。
    """
    pool = get_pool()
    rejected_id = req.rejected_id or None
    if not rejected_id and req.job_family:
        # 未指定放弃者时，默认取该岗位族当前排名第一作为「已发 offer 后放弃」的演示对象
        top = pool.rank(req.job_family)
        if top:
            rejected_id = top[0].candidate_id
    try:
        out = pool.handle_offer_rejection(req.job_family or None, rejected_id)
    except Exception as e:  # noqa: BLE001
        return {"success": False, "error": str(e)}
    return {"success": True, **out}


# ---------- 模块 1：JD 自动生成 + HR/用人部门可编辑 ----------
@app.post("/jd/generate")
def jd_generate(req: JdGenerateReq):
    """岗位族模板 + 参数 → 可编辑结构化 JD（PRD 模块 1：自动生成 JD 且 HR/用人部门可改）。"""
    try:
        jd = generate_jd(req.job_family, req.params or {})
    except KeyError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "job_family": req.job_family, "jd": jd}


@app.post("/jd/save")
def jd_save(req: JdGenerateReq):
    """保存（HR/用人部门修改后的）JD，best-effort 写回飞书「招聘需求表」。"""
    from config import JD_TABLE_ID
    if not JD_TABLE_ID:
        return {"success": False, "error": "未配置 JD_TABLE_ID，无法写回飞书"}
    try:
        jd = generate_jd(req.job_family, req.params or {})
    except KeyError as e:
        return {"success": False, "error": str(e)}
    fields = {
        "岗位名称": jd.get("position", ""),
        "城市": jd.get("location", ""),
        "薪资": jd.get("salary", ""),
        "岗位描述": "；".join(jd.get("responsibilities", [])) or jd.get("job_family", ""),
        "任职资格": "；".join(jd.get("requirements_hard", [])),
    }
    try:
        from src.matcher_v2 import FeishuClient
        r = FeishuClient().create_records(JD_TABLE_ID, [fields])
        ok = r.get("code") == 0
    except Exception as e:  # noqa: BLE001
        return {"success": False, "error": f"写回飞书失败：{e}"}
    return {"success": ok, "feishu_result": r, "jd": jd}


# ---------- 模块 1 终点：HR↔用人部门双向推送审批流 ----------
@app.post("/review/department-push")
def department_push(req: DepartmentPushReq):
    """HR 将已初筛候选人推送给用人部门复核（双向回环起点）。

    状态机：储备/备选 → 待部门复核；best-effort 写回飞书 + 群机器人通知用人部门。
    """
    pool = get_pool()
    rec = pool.get(req.candidate_id) if req.candidate_id else None
    if rec is not None:
        rec.status = "待部门复核"
        pool._update_feishu(rec)

    pushed = False
    try:
        from src.feishu_client import FeishuClient as BotClient
        webhook = os.getenv("FEISHU_BOT_WEBHOOK", "")
        if webhook:
            text = (f"【待您复核 · {req.job_family or '通用'}】\n"
                    f"候选人：{req.name or req.candidate_id}\n"
                    f"→ 请在人才评价汇总页完成「通过 / 不通过 + 备注」。")
            BotClient().send_bot_text(webhook, text)
            pushed = True
    except Exception:
        pushed = False

    return {"success": True, "candidate_id": req.candidate_id,
            "status": rec.status if rec else "待部门复核",
            "dept_pushed": pushed,
            "message": "已推送用人部门复核"}


@app.post("/review/department-decision")
def department_decision(req: DepartmentDecisionReq):
    """用人部门对筛选结论复核：通过/不通过 + 备注 → 回写人才池状态并推送 HR 电话初面。"""
    from datetime import datetime
    record = {
        "candidate_id": req.candidate_id,
        "name": req.name,
        "job_family": req.job_family,
        "decision": req.decision,
        "note": req.note,
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    DEPARTMENT_DECISIONS.append(record)

    # 回写人才池状态（双向回环闭环）：通过 → 部门通过·待HR初面；不通过 → 部门驳回
    pool = get_pool()
    rec = pool.get(req.candidate_id) if req.candidate_id else None
    if rec is not None:
        rec.status = "部门通过-待HR初面" if req.decision == "通过" else "部门驳回"
        pool._update_feishu(rec)

    # 群机器人推送 HR（若已配置 webhook）
    pushed = False
    try:
        from src.feishu_client import FeishuClient as BotClient
        webhook = os.getenv("FEISHU_BOT_WEBHOOK", "")
        if webhook:
            text = (f"【用人部门复核 · {req.job_family or '通用'}】\n"
                    f"候选人：{req.name or req.candidate_id}\n"
                    f"结论：{req.decision}\n"
                    f"备注：{req.note or '（无）'}\n"
                    f"→ 请 HR 安排电话初面 / 跟进。")
            BotClient().send_bot_text(webhook, text)
            pushed = True
    except Exception:
        pushed = False

    return {"success": True, "record": record, "hr_pushed": pushed,
            "pool_status": rec.status if rec else None,
            "message": "已记录用人部门意见并推送 HR 电话初面" if req.decision == "通过"
                       else "已记录用人部门驳回意见并退回 HR"}


@app.get("/review/decisions")
def review_decisions():
    """查看已记录的用人部门复核意见。"""
    return {"count": len(DEPARTMENT_DECISIONS), "decisions": DEPARTMENT_DECISIONS}


# ---------- 黑客松开箱即跑：灌入结构化「特色简历」演示数据 ----------
@app.post("/demo/seed")
def demo_seed():
    """向内存人才池灌入 6 份内置结构化特色候选人（优质/稳定/风险各异），
    保证前端「人才评价汇总 + Offer 递补」离线即可演示，且分数/等级可信。"""
    pool = get_pool()
    # 清空演示用池（仅清内存，绝不碰飞书表），避免重复灌入
    from src.talent_pool import TalentPool
    new_pool = TalentPool()
    import src.talent_pool as _tp
    _tp.pool = new_pool

    demo = [
        ("张伟", "firstline", "装配包装工", 94, "A级", "低", [], "对口·稳定·到岗快", ["合格", "优先推荐"]),
        ("李娜", "firstline", "质检员", 88, "B级", "中", [{"type": "频繁跳槽"}], "经验足·稳定性待核", ["合格", "储备"]),
        ("王强", "firstline", "设备操作工", 83, "B级", "低", [], "技能匹配·倒班OK", ["合格", "储备"]),
        ("赵敏", "firstline", "装配包装工", 77, "C级", "中", [{"type": "证书核验"}], "证书有效期待核", ["备选", "待确认"]),
        ("陈浩", "firstline", "设备操作工", 71, "C级", "高", [{"type": "工作经历断层"}], "空窗期待核", ["备选", "待确认"]),
        ("周婷", "firstline", "质检员", 65, "C级", "中", [], "基本对口·待面试确认", ["备选", "待确认"]),
    ]
    pooled = 0
    for name, fam, job, score, grade, risk, rp, summary, tags in demo:
        res = new_pool.auto_intake(name, fam, job, score, grade, risk, rp, summary)
        if res.get("pooled"):
            pooled += 1
    return {"success": True, "seeded": len(demo), "pooled": pooled,
            "comparison": new_pool.comparison_matrix()}
