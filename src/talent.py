"""
人才评价模块
============
候选人横向对比 + 招聘进度跟踪，写回飞书「招聘进度管理」表。
"""
from __future__ import annotations


def compare_candidates(scored: list) -> dict:
    """多候选人横向对比：匹配度/等级/风险/软条件。"""
    rows = []
    for c in scored:
        rows.append({
            "候选人": c.get("候选人"),
            "匹配度": c.get("匹配度"),
            "等级": c.get("等级"),
            "风险等级": c.get("风险等级"),
            "匹配总结": c.get("匹配总结"),
        })
    return {"候选人数": len(rows), "对比表": rows}


def format_compare_text(compare: dict) -> str:
    lines = [f"候选人横向对比（共 {compare['候选人数']} 人）", ""]
    for r in compare["对比表"]:
        lines.append(f"  {r['候选人']} → {r['匹配度']}分 · {r['等级']} · 风险{r['风险等级']}")
    return "\n".join(lines)


def write_progress(feishu, job_name: str, demand: int = 0, status: str = "招聘中") -> dict:
    """写飞书「招聘进度管理」表：岗位 + 需求人数 + 当前状态。"""
    from config import PROGRESS_TABLE_ID
    fields = {
        "岗位名称": job_name,
        "需求人数": demand,
        "当前状态": status,
    }
    return feishu.create_records(PROGRESS_TABLE_ID, [fields])


if __name__ == "__main__":
    print(format_compare_text(compare_candidates([
        {"候选人": "候选人A", "匹配度": 92, "等级": "A级", "风险等级": "中", "匹配总结": "装配工对口"},
        {"候选人": "张三", "匹配度": 60, "等级": "C级", "风险等级": "低", "匹配总结": "经验不足"},
    ])))
