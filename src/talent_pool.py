"""
人才储备池（模块 4 核心）
=======================
把通过初筛的合格候选人自动入库、打标签、跨岗位族复用；
当选定候选人放弃 Offer 时，按匹配度顺位秒级推举下一合适候选人（Offer 递补）。

设计：
- 进程内 InMemoryTalentPool 作为「实时决策源」，保证演示不依赖飞书凭证也能跑通主干。
- 若配置了 TALENT_POOL_TABLE_ID，则把入库/状态变更 best-effort 写回飞书「人才储备池」表，
  并在 Offer 放弃时通过群机器人推送递补汇总（真实对接飞书）。
- 所有飞书写操作都包 try/except，飞书不可达不影响主流程。

状态机：储备(available) → 已发offer(selected) → 已放弃offer(rejected) / 已入职(hired)
"""
from __future__ import annotations
import os
import sys
import time
import uuid
import pathlib

# 与 api/server.py 导入方式一致，确保人才池/FeishuClient 单例全局唯一
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))        # src/
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent)) # 项目根（config）

import config

# 群机器人 webhook（可选）。与 feishu_client.py 保持一致：统一从环境变量读取，
# 避免对未定义模块级常量的硬依赖（feishu_client 内也只用 os.getenv 读取）。
FEISHU_BOT_WEBHOOK = os.getenv("FEISHU_BOT_WEBHOOK", "")

# 备注：TALENT_POOL_TABLE_ID 在运行时按 config.TALENT_POOL_TABLE_ID 读取（而非导入期绑定常量），
# 以便演示时动态设置表 id 也无需重启进程。


# 等级 → 入库标签（PRD：合格候选人自动入库、分类标签管理）
GRADE_TAG = {
    "A级": ["合格", "优先推荐"],
    "B级": ["合格", "储备"],
    "C级": ["备选", "待确认"],
    "不推荐": [],  # 不入库
}


class CandidateRecord:
    """人才池中的一条候选人记录。"""

    def __init__(self, candidate_id: str, name: str, job_family: str, job_name: str,
                 match_score, grade: str, risk_level: str, risk_points: list,
                 summary: str, tags: list = None, feishu_record_id: str = ""):
        self.candidate_id = candidate_id
        self.name = name
        self.job_family = job_family
        self.job_name = job_name
        self.match_score = match_score
        self.grade = grade
        self.risk_level = risk_level
        self.risk_points = risk_points or []
        self.summary = summary
        self.tags = tags or []
        self.status = "储备"          # 储备 / 已发offer / 已放弃offer / 已入职
        self.intake_at = time.strftime("%Y-%m-%d %H:%M:%S")
        self.feishu_record_id = feishu_record_id or ""

    def to_feishu_fields(self) -> dict:
        # 等级/风险等级/状态 用「文本」写入（与项目评分结果表一致，避免 single_select 转换失败）
        return {
            "候选人": self.name,
            "岗位族": self.job_family,
            "应聘岗位": self.job_name,
            "匹配度": self.match_score if self.match_score is not None else 0,
            "等级": self.grade,
            "风险等级": self.risk_level,
            "标签": "、".join(self.tags),
            "状态": self.status,
            "匹配总结": self.summary,
            "入库时间": self.intake_at,
        }

    def to_comparison_row(self) -> dict:
        """PRD 模块 4 对比表行（comparisonMatrix）。"""
        return {
            "candidateId": self.candidate_id,
            "name": self.name,
            "jobFamily": self.job_family,
            "jobName": self.job_name,
            "totalScore": self.match_score,
            "grade": self.grade,
            "riskLevel": self.risk_level,
            "tags": self.tags,
            "status": self.status,
            "summary": self.summary,
        }


class TalentPool:
    """进程内人才储备池（单例）。"""

    def __init__(self):
        self._by_id: dict[str, CandidateRecord] = {}

    # ---------- 入库 ----------
    def auto_intake(self, name: str, job_family: str, job_name: str,
                    match_score, grade: str, risk_level: str,
                    risk_points: list, summary: str) -> dict:
        """合格候选人自动入库 + 分类标签。返回 {candidate_id, tags, status, pooled}。"""
        tags = GRADE_TAG.get(grade, [])
        pooled = bool(tags)  # 不推荐不入库
        candidate_id = f"C-{uuid.uuid4().hex[:8]}"
        rec = CandidateRecord(candidate_id, name, job_family, job_name,
                              match_score, grade, risk_level, risk_points, summary, tags)
        # 状态：A/B 级入库为「储备」，C 级为「备选」
        rec.status = "储备" if grade in ("A级", "B级") else "备选"
        if pooled:
            self._by_id[candidate_id] = rec
            self._write_feishu(rec)
        return {
            "candidate_id": candidate_id,
            "name": name,
            "tags": tags,
            "status": rec.status,
            "pooled": pooled,
            "feishu_record_id": rec.feishu_record_id,
        }

    def update_status(self, candidate_id: str, status: str) -> bool:
        rec = self._by_id.get(candidate_id)
        if not rec:
            return False
        rec.status = status
        self._update_feishu(rec)
        return True

    # ---------- 查询 / 对比 ----------
    def rank(self, job_family: str = None) -> list:
        """同岗位族（或全量）按匹配度降序返回记录。"""
        recs = [r for r in self._by_id.values()
                if (job_family is None or r.job_family == job_family)]
        return sorted(recs, key=lambda r: (r.match_score or 0), reverse=True)

    def comparison_matrix(self, job_family: str = None) -> list:
        """PRD 模块 4：候选人对标信息对比表。"""
        return [r.to_comparison_row() for r in self.rank(job_family)]

    def get(self, candidate_id: str) -> CandidateRecord | None:
        return self._by_id.get(candidate_id)

    # ---------- 核心：Offer 放弃秒级递补 ----------
    def handle_offer_rejection(self, job_family: str, rejected_id: str = None) -> dict:
        """
        指定候选人放弃 Offer → 同岗位族按匹配度顺位推举下一合适候选人。
        返回 {triggered, rejected, next_best, fallback_reason, comparison, feishu_pushed}。
        """
        rejected = None
        if rejected_id:
            rejected = self._by_id.get(rejected_id)
            if rejected:
                if rejected.status in ("储备", "已发offer"):
                    rejected.status = "已放弃offer"
                    self._update_feishu(rejected)
            else:
                return {"triggered": False, "error": f"未找到候选人 {rejected_id}"}

        # 同岗位族、可用（储备/备选）候选人，按匹配度降序；已发offer/已放弃offer 不参与递补
        available = [r for r in self.rank(job_family)
                     if r.status in ("储备", "备选") and r.grade in ("A级", "B级", "C级")]
        available.sort(key=lambda r: (r.match_score or 0), reverse=True)

        if not available:
            reason = (f"同岗位族「{job_family}」暂无其他合格候选人可递补"
                      f"（已储备 {len(self.rank(job_family))} 人，均不可用）。")
            self._push_fallback(rejected, None, reason, job_family)
            return {
                "triggered": True,
                "rejected": rejected.to_comparison_row() if rejected else None,
                "next_best": None,
                "fallback_reason": reason,
                "comparison": self.comparison_matrix(job_family),
                "feishu_pushed": bool(FEISHU_BOT_WEBHOOK),
            }

        next_best = available[0]
        next_best.status = "已发offer"   # 锁定，避免重复递补
        self._update_feishu(next_best)

        fam_count = len(self.rank(job_family))
        rejected_name = rejected.name if rejected else "（未指定）"
        tags_txt = "、".join(next_best.tags) or "无"
        reason = (f"原定候选人「{rejected_name}」放弃 Offer；"
                  f"同岗位族共 {fam_count} 人在池，按匹配度顺位推举下一顺位："
                  f"「{next_best.name}」（{next_best.match_score}分 / {next_best.grade} / 风险{next_best.risk_level}），"
                  f"标签：{tags_txt}。")
        self._push_fallback(rejected, next_best, reason, job_family)
        return {
            "triggered": True,
            "rejected": rejected.to_comparison_row() if rejected else None,
            "next_best": next_best.to_comparison_row(),
            "fallback_reason": reason,
            "comparison": self.comparison_matrix(job_family),
            "feishu_pushed": bool(FEISHU_BOT_WEBHOOK),
        }

    # ---------- 飞书 best-effort 写回 ----------
    def _feishu(self):
        if not config.TALENT_POOL_TABLE_ID:
            return None
        try:
            from src.matcher_v2 import FeishuClient
            return FeishuClient()
        except Exception:
            return None

    def _write_feishu(self, rec: CandidateRecord):
        fc = self._feishu()
        if not fc:
            return
        try:
            r = fc.create_records(config.TALENT_POOL_TABLE_ID, [rec.to_feishu_fields()])
            if r.get("code") == 0 and r.get("data", {}).get("records"):
                rec.feishu_record_id = r["data"]["records"][0]["record_id"]
        except Exception:
            pass  # best-effort

    def _update_feishu(self, rec: CandidateRecord):
        fc = self._feishu()
        if not fc or not rec.feishu_record_id:
            return
        try:
            fc.update_record(config.TALENT_POOL_TABLE_ID, rec.feishu_record_id,
                             {"状态": rec.status})
        except Exception:
            pass

    def _push_fallback(self, rejected, next_best, reason: str, job_family: str):
        if not FEISHU_BOT_WEBHOOK:
            return
        try:
            from src.feishu_client import FeishuClient as BotClient
            lines = [f"【Offer 递补提醒 · {job_family}】", reason]
            if next_best:
                lines.append(f"→ 请 HR / 用人部门推进「{next_best.name}」的 Offer 流程。")
            else:
                lines.append("→ 建议扩大简历库或发起新一轮筛选。")
            BotClient().send_bot_text(FEISHU_BOT_WEBHOOK, "\n".join(lines))
        except Exception:
            pass


# 进程级单例（跨请求持久）
pool = TalentPool()


def get_pool() -> TalentPool:
    return pool


if __name__ == "__main__":
    # 自测：模拟一条可演示链路
    p = TalentPool()
    p.auto_intake("张三", "firstline", "装配包装工", 92, "A级", "低", [], "对口·稳定")
    p.auto_intake("李四", "firstline", "装配包装工", 85, "B级", "中", [{"type": "频繁跳槽"}], "经验足·稳定待核")
    p.auto_intake("王五", "firstline", "装配包装工", 78, "C级", "低", [], "基本对口")
    print("入库后排名：")
    for r in p.rank("firstline"):
        print(f"  {r.name} {r.match_score} {r.grade} {r.status} {r.tags}")
    print("\n触发 Offer 放弃（张三）：")
    out = p.handle_offer_rejection("firstline", p.rank("firstline")[0].candidate_id)
    print("  递补理由：", out["fallback_reason"])
    print("  下一顺位：", out["next_best"]["name"] if out["next_best"] else None)
