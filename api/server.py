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
from pydantic import BaseModel

from src.llm_resume_parser import parse_resume_with_llm, llm_result_to_feishu_fields
from src.matcher_v2 import run_matching

app = FastAPI(title="海信 AI 招聘智能体 API", version="1.0", description="简历解析 + 人岗匹配评分")


class ResumeText(BaseModel):
    text: str


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
