# 海信容声 — AI 招聘智能体

> 顺德 AI 黑客松（企业命题赛道）｜海信容声（广东）冰箱有限公司

**赛题**：人力资源管理 AI 智能体（招聘方向）

一个全流程自动化、高精准度的招聘甄选 AI 智能体，替代人工完成简历筛选、面试辅助、人才评价汇总等工作。

## 四大业务模块（赛题）

1. **简历筛选** — JD 生成 + 多维度匹配权重 + 0-100 评分 + 硬/软条件区分
2. **风险识别与资质核验** — 简历造假 / 工作断层 / 证书过期 / 频繁跳槽 + 技能真实性核验
3. **面试辅助** — 结构化题库 + 个性化问题 + 纪要 + 打分评级
4. **人才评价汇总** — 候选人对比表 + 决策辅助 + 人才库复用 + offer 弃权替补推送

原始赛题资料见 [`docs/hisense-ai-recruitment-agent.md`](docs/hisense-ai-recruitment-agent.md)。

## 团队

4 人团队，分工待定（确定后更新本节）。

## 项目结构（Spec Kit 规范驱动）

```
.
├── .specify/                  # Spec Kit 配置
│   ├── memory/
│   │   └── constitution.md    # 项目宪法（工程原则，spec 需逐条对照）
│   └── templates/             # spec / plan / tasks / checklist 模板
├── specs/                     # 功能规格文档（按编号组织）
├── docs/                      # 项目原始资料
└── README.md
```

## 开发工作流（Spec Kit）

1. **写规格** — 在 `specs/###-feature/` 下新建 `spec.md`
2. **写计划** — 基于规格写 `plan.md`
3. **拆任务** — 写 `tasks.md` 并逐条完成
4. **提 PR** — feature 分支 → `main`（评审后合并）

## 协作约定

- `main` 分支受保护，通过 PR 合并
- feature 分支命名：`###-feature-name`（与 spec 编号对应）
- 提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/)：`feat` / `fix` / `refactor` / `docs` / `test` / `chore`

## 加入协作

```bash
gh repo clone MarlinFreesoul/hisense-ai-recruitment-agent
```

团队其他成员的协作权限由仓库管理员添加（GitHub → Settings → Collaborators）。
