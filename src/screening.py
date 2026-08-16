"""
上传即打分（模块 1 闭环 · 不依赖飞书即可跑通）
=========================================
接收简历文本（LLM 解析 / 离线正则兜底）或结构化字段 + 岗位族/岗位名，
复用 matcher_v2 的确定性三态引擎打分（0-100），并把合格候选人自动入人才池。

数据流：
  简历文本 → (LLM 解析 → 飞书字段) | 结构化字段
           → feishu_to_resume → resume 结构
           → score_feishu_resume（硬条件一票否决 + 软条件加权 + 风险）
           → 合格(A/B) 自动入人才池（talent_pool.auto_intake）
           → best-effort 写回飞书「评分结果表」+「人才储备池」表
"""
from __future__ import annotations
import re

# 与 api/server.py 保持一致用 src. 前缀导入，确保模块单例（人才池/FeishuClient）全局唯一
from src.matcher_v2 import (match_job_family, load_weights_from_feishu, apply_feishu_weights,
                            feishu_to_resume, score_feishu_resume, FeishuClient)
from jd_generator import load_family  # matcher_v2 导入时已把 src/ 加入 sys.path，故可顶层导入
from src.talent_pool import get_pool
from config import RESULT_TABLE_ID, TALENT_POOL_TABLE_ID


# ============== 简历文本 → 飞书字段（解析层） ==============
def parse_text_to_feishu_fields(text: str, api_key: str = None) -> dict:
    """简历文本 → 飞书简历库字段。

    - 有 DeepSeek key：走 LLM 解析（非标主路径）。
    - 无 key / 解析失败：离线正则兜底，保证演示不依赖外部服务。
    """
    parsed = None
    if api_key:
        try:
            from llm_resume_parser import parse_resume_with_llm, llm_result_to_feishu_fields
            parsed = parse_resume_with_llm(text, api_key=api_key)
            return llm_result_to_feishu_fields(parsed)
        except Exception:
            parsed = None
    return _parse_text_local(text)


def _parse_text_local(text: str) -> dict:
    """极简离线解析：从文本抽关键字段，映射到飞书简历库字段。仅用于无 LLM 时的兜底演示。"""
    t = text or ""
    fields = {
        "姓名": "", "手机号": "", "邮箱": "",
        "最高学历": "", "毕业院校": "", "专业": "", "工作年限": 0,
        "最近公司": "", "最近职位": "", "核心技能": [], "工作经历简述": "",
        "证书": "", "自我评价": "", "期望到岗": "",
    }
    # 姓名：常见「姓名：xxx」或首行
    m = re.search(r"姓名[：:]\s*([^\s，,。\n]{2,4})", t)
    if m:
        fields["姓名"] = m.group(1)
    # 学历
    for deg in ["博士", "硕士", "本科", "大专", "中专", "高中", "初中及以下"]:
        if deg in t:
            fields["最高学历"] = deg
            break
    # 工作年限
    m = re.search(r"(\d+(?:\.\d+)?)\s*年", t)
    if m:
        fields["工作年限"] = float(m.group(1))
    # 技能：包含这些关键词
    skill_kw = ["电工证", "钳工证", "焊工", "叉车", "PLC", "CAD", "质检", "ISO", "精益", "倒班", "夜班"]
    fields["核心技能"] = [k for k in skill_kw if k in t]
    # 证书
    certs = re.findall(r"([\u4e00-\u9fa5]{2,5}证(?:书|件)?)", t)
    if certs:
        fields["证书"] = "、".join(certs)
    # 到岗
    if "一个月内" in t or "随时" in t or "立即" in t:
        fields["期望到岗"] = "1个月内到岗"
    # 自我评价/倒班意愿
    if "倒班" in t or "夜班" in t:
        fields["自我评价"] = "接受倒班"
    fields["工作经历简述"] = t[:100]
    return fields


# ============== 主流程 ==============
def screen_resume(text: str = None, resume: dict = None, job_family: str = None,
                  job_name: str = None, *, intake: bool = True,
                  write_feishu: bool = True) -> dict:
    """上传即打分 + 自动入池。

    参数：
      text      简历原文（优先走 LLM，无 key 走离线兜底）
      resume    结构化飞书字段风格 dict（与 text 二选一；若同时给 text 优先）
      job_family 岗位族 key（firstline / process-equipment ...）；不传则按 job_name 推断
      job_name  岗位名（用于推断岗位族 + 结果展示）
      intake    是否自动入人才池（默认 True）
      write_feishu 是否 best-effort 写回飞书（默认 True）
    返回：{ candidate_id?, job_family, job_name, result(评分契约), talent_pool(入池结果) }
    """
    from config import DEEPSEEK_API_KEY

    # 1) 解析简历 → 飞书字段 → resume 结构
    if text and text.strip():
        feishu_fields = parse_text_to_feishu_fields(text, DEEPSEEK_API_KEY or None)
    elif resume:
        feishu_fields = resume
    else:
        raise ValueError("需提供 text（简历原文）或 resume（结构化字段）其中之一")
    rv = feishu_to_resume(feishu_fields)

    # 2) 确定岗位族
    family_key = job_family or (match_job_family(job_name) if job_name else None)
    if not family_key:
        raise ValueError(f"无法识别岗位族：请提供 job_family 或在 job_name 中包含已知岗位关键词（{job_name}）")
    family = load_family(family_key)

    # 3) 权重（飞书优先，失败则默认）
    try:
        fc = FeishuClient()
        weights = load_weights_from_feishu(fc)
        family = apply_feishu_weights(family, weights.get(family_key, {}))
    except Exception:
        pass

    # 4) 确定性打分
    result = score_feishu_resume(rv, family)
    result["候选人"] = rv.get("name") or "未命名候选人"
    result["岗位"] = job_name or family.get("representative", [""])[0]

    # 5) 自动入人才池（合格 A/B 入库；C 作备选；不推荐不入库）
    talent_out = {"pooled": False}
    if intake:
        tp = get_pool()
        talent_out = tp.auto_intake(
            name=result["候选人"],
            job_family=family_key,
            job_name=result["岗位"],
            match_score=result.get("匹配度"),
            grade=result.get("等级"),
            risk_level=result.get("风险等级"),
            risk_points=result.get("风险点", []),
            summary=result.get("匹配总结", ""),
        )
        result["candidate_id"] = talent_out.get("candidate_id")

    # 6) best-effort 写回飞书「评分结果表」
    if write_feishu and RESULT_TABLE_ID:
        try:
            fc = FeishuClient()
            fc.create_records(RESULT_TABLE_ID, [{
                "候选人": result["候选人"], "岗位名称": result["岗位"],
                "匹配度": result.get("匹配度"), "等级": result.get("等级"),
                "风险等级": result.get("风险等级"), "匹配总结": result.get("匹配总结"),
                "推荐结论": "通过筛选" if result.get("等级") in ("A级", "B级") else "待定",
            }])
        except Exception:
            pass

    return {
        "candidate_id": talent_out.get("candidate_id"),
        "job_family": family_key,
        "job_name": result["岗位"],
        "result": result,
        "talent_pool": talent_out,
    }


if __name__ == "__main__":
    # 离线自测（不需要 LLM / 飞书）
    sample = "姓名：陈浩。本科，机械制造专业，5 年设备维修经验，持有电工证、钳工证，接受倒班，随时到岗。"
    out = screen_resume(text=sample, job_name="设备维修工程师", write_feishu=False)
    r = out["result"]
    print(f"候选人：{r['候选人']} | 匹配度：{r['匹配度']} | 等级：{r['等级']} | 风险：{r['风险等级']}")
    print("入池：", out["talent_pool"])
