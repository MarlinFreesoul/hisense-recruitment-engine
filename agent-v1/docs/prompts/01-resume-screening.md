# 提示词 ①:简历筛查节点(可解释匹配)

> 给:罗应杰 ｜ 模块① 简历筛选 ｜ 产出 `src/screening.py`(已有一版规则版,本提示词是深化)

## 项目背景

海信容声「AI 招聘智能体」黑客松项目。整体是**多级漏斗**:

```
简历PDF → 解析 → 简历结构化 → ①筛查(你在这) → ②风险 → ③面试 → ④汇总 → 人工终判
```

你是**入口 + 第一痛点**:赛题痛点「简历筛选效率低、人岗匹配主观化」就由你解决。

## 你的任务

把 `src/screening.py` 从"规则版 v1"深化成**可解释匹配**。核心不是给一个 0-100 黑箱分,而是:

1. **硬条件逐条 check**(确定性,不靠 LLM):学历/经验/年龄/技能/证书
2. **软条件评分 + 证据**(LLM,每条必须有"证据")
3. **输出短板** `gaps`(喂给③面试模块出个性化题)

## 输入(上游「简历结构化」产出的简历 JSON)

```json
{
  "name": "张三", "age": 28, "education": "硕士",
  "school": "广东海洋大学", "major": "计算机",
  "experience_years": 5, "skills": ["Python", "STM32", "C语言"],
  "work_history": [{"company": "某公司", "role": "嵌入式工程师", "years": 3}],
  "certificates": ["软考中级"]
}
```

JD 用 `data/jobs/` 里结构化好的(硬条件 `hard` + 软条件 `soft`):

```json
{
  "title": "嵌入式高级软件开发工程师",
  "hard": [{"field": "学历", "requirement": "本科"}, {"field": "经验", "requirement": "5年"}, {"field": "技能", "requirement": "STM32"}],
  "soft": ["嵌入式", "制冷", "ARM"]
}
```

## 输出(你要产出的 JSON)

```json
{
  "hard_pass": true,
  "hard_checks": [{"field": "学历", "requirement": "本科", "matched": true, "extracted": "硕士", "evidence": "简历含'硕士'"}],
  "soft_scores": [{"dim": "嵌入式", "score": 0.8, "evidence": "5年嵌入式经验"}],
  "overall": 85.0,
  "gaps": ["缺PCB经验"],
  "explanation": "硬条件全通过,软条件命中50%,总分85"
}
```

## 硬性要求

- **可解释**:每个评分/判断都要带 `evidence`,不许只输出一个分数(HackerRank 教训:纯 LLM 打分同一简历 66~99 波动)
- **低成本**:硬条件用规则;软条件 LLM 只用 DeepSeek(便宜),能不用 LLM 就不用
- 小文件 + 不可变(不原地 mutate)+ 中文注释
- 能独立运行:`python3 src/screening.py` 跑通示例

## 完成标准

- [ ] `python3 src/screening.py` 跑通,输出符合上面的 JSON
- [ ] 硬条件用确定性规则,软条件带证据
- [ ] 产出的 `gaps` 能直接作为③面试模块的输入
