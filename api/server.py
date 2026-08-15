"""
API 服务（FastAPI）
==================
同事 / 前端通过 HTTP 调用后端能力，不用碰内部代码。

启动：uvicorn api.server:app --host 0.0.0.0 --port 8000
同事访问：http://<你的IP>:8000/docs （自动生成的接口文档）
"""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.llm_resume_parser import parse_resume_with_llm, llm_result_to_feishu_fields
from src.matcher_v2 import run_matching
from src.interview_collect import generate_core_questions

app = FastAPI(title="海信 AI 招聘智能体 API", version="1.0", description="简历解析 + 人岗匹配评分")

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


class InterviewSubmit(BaseModel):
    candidate: str = ""
    job: str = ""
    answers: dict = {}


@app.get("/health")
def health():
    return {"status": "ok", "service": "海信 AI 招聘智能体"}


@app.post("/parse_resume")
def parse_resume(req: ResumeText):
    """简历文本 → 结构化字段（LLM 解析，适配非标简历）。"""
    parsed = parse_resume_with_llm(req.text)
    return {"parsed": parsed, "feishu_fields": llm_result_to_feishu_fields(parsed)}


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
def interview_questions(candidate: str = ""):
    """读简历 + 风险点 → 生成核心采集问题（参数化）。"""
    from src.matcher_v2 import FeishuClient, feishu_to_resume, match_job_family
    from src.risk_filter import risk_report
    from config import RESUME_TABLE_ID
    feishu = FeishuClient()
    records = feishu.get_records(RESUME_TABLE_ID)
    rec = next((r for r in records if r["record_id"] == candidate or r["fields"].get("姓名") == candidate), None)
    if not rec:
        return {"error": "未找到候选人，请传 candidate=record_id 或姓名"}
    resume = feishu_to_resume(rec["fields"])
    risk = risk_report(resume)
    risk_points = [r for r in risk["risks"] if r["level"] != "低"]
    family_key = match_job_family(rec["fields"].get("最近职位", "")) or "firstline"
    questions = generate_core_questions(family_key, resume, risk_points)
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
