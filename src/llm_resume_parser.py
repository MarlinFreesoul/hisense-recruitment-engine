"""
LLM 简历解析（DeepSeek）
========================
非标简历（格式混乱/信息不全）→ LLM 提取结构化字段 → 对齐飞书简历库 11 字段。
规则版 resume_parser.py 作为兜底，本模块是主路径。
"""
from __future__ import annotations
import json
import re
import requests

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


def parse_resume_with_llm(resume_text: str, api_key: str = None) -> dict:
    """LLM 解析简历文本 → 结构化字段（对齐飞书简历库字段）。"""
    key = api_key or DEEPSEEK_API_KEY
    if not key:
        raise ValueError("未配置 DEEPSEEK_API_KEY，无法 LLM 解析")

    prompt = f"""你是一个专业的简历解析助手。请从以下简历内容中提取关键信息，以 JSON 返回。

字段说明（缺的信息填空字符串或空数组）：
- 姓名、手机号、邮箱
- 最高学历：博士/硕士/本科/大专/中专/高中/初中及以下（只填这些标准词）
- 毕业院校、专业（教育专业，如「机械制造」）
- 工作年限：数字（年）
- 最近公司、最近职位
- 核心技能：数组，最多 5 个
- 工作经历简述：不超过 100 字
- 证书：数组，如 ["电工证","钳工证"]
- 自我评价：原文中的自我评价/优势（保留「能吃苦耐劳」「接受倒班」等关键词）
- 期望到岗：如「1个月内到岗」

只返回 JSON，不要其他内容：
{{"姓名":"","手机号":"","邮箱":"","最高学历":"","毕业院校":"","专业":"","工作年限":0,"最近公司":"","最近职位":"","核心技能":[],"工作经历简述":"","证书":[],"自我评价":"","期望到岗":""}}

简历内容：
---
{resume_text[:4000]}
---
"""
    resp = requests.post(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": DEEPSEEK_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1},
        timeout=60,
    )
    data = resp.json()
    if "choices" not in data:
        raise Exception(f"LLM 调用失败: {data}")
    content = data["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if not m:
        raise Exception(f"LLM 返回无 JSON: {content[:200]}")
    return json.loads(m.group())


def llm_result_to_feishu_fields(parsed: dict) -> dict:
    """LLM 解析结果 → 飞书简历库字段。"""
    return {
        "姓名": parsed.get("姓名", "") or "",
        "手机号": parsed.get("手机号", "") or "",
        "邮箱": parsed.get("邮箱", "") or "",
        "最高学历": parsed.get("最高学历", "") or "",
        "毕业院校": parsed.get("毕业院校", "") or "",
        "专业": parsed.get("专业", "") or "",
        "工作年限": parsed.get("工作年限", 0) or 0,
        "最近公司": parsed.get("最近公司", "") or "",
        "最近职位": parsed.get("最近职位", "") or "",
        "核心技能": parsed.get("核心技能", []) or [],
        "工作经历简述": parsed.get("工作经历简述", "") or "",
        "证书": "、".join(parsed.get("证书", []) or []),
        "自我评价": parsed.get("自我评价", "") or "",
        "期望到岗": parsed.get("期望到岗", "") or "",
    }


if __name__ == "__main__":
    import sys
    txt = sys.stdin.read() if not sys.stdin.isatty() else ""
    if not txt:
        print("用法: echo '简历文本' | python src/llm_resume_parser.py")
    else:
        print(json.dumps(parse_resume_with_llm(txt), ensure_ascii=False, indent=2))
