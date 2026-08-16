# 海信容声 AI 招聘智能体 · 角色训练仓库

> PromptX 角色训练仓库:7 个招聘领域专家角色 + 知识底座 + 模块 prompt。
> 与后端仓库 [hisense-ai-recruitment.backend](https://github.com/Jasper-Leung/hisense-ai-recruitment.backend) 分离。

## 目录结构

```
roles/           # 7 个角色的"胚胎"定义(练角色的起点)
prompts/         # 4 个模块 prompt(角色执行任务时用)
data/            # 知识底座:131 条结构化 JD + 字段频率表
docs/            # 架构 + 漏斗契约 + 赛题原文
```

## 角色清单(顺德招聘系统开发部)

| 角色 | handle | 定位 |
|---|---|---|
| HR 招聘领域专家 | `shunde-hr-expert` | 领域顾问 |
| 招聘系统架构师 | `shunde-architect` | 漏斗 + 契约 + 集成 |
| 招聘数据工程师 | `shunde-data` | 数据底座 |
| 简历筛查工程师 | `shunde-screening` | 模块① 可解释匹配 |
| 风险识别审计师 | `shunde-risk` | 模块② 造假/断层/合规 |
| AI 面试官设计专家 | `shunde-interview` | 模块③ 岗位模型+题库 |
| 人才评价专家 | `shunde-talent` | 模块④ 人才库+汇总 |

## 练角色的方法

> PromptX 的核心哲学:"角色不是写出来的,是对话出来的。"

1. 每个 `roles/*.md` 是**胚胎**(定位 + 职责 + 边界 + 方法),不是成品
2. 通过对话逐步长出血肉:喂真实招聘场景、追问边界、注入知识库
3. 最终落成 PromptX 的 DPML 格式,接入本地 mcp-server

## 知识底座

- `data/jobs.json` — 131 条结构化岗位(硬条件/软条件/职责/任职资格,已清洗)
- `data/field_frequency.csv` — 字段频率表(扫一眼看脏值)
