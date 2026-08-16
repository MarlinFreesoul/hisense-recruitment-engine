# 提示词 ④:人才评价汇总 + 人才库节点

> 给:队友 D ｜ 模块④ 人才评价汇总 ｜ 产出 `src/talent_pool.py`

## 项目背景

海信容声「AI 招聘智能体」黑客松项目。多级漏斗:

```
简历PDF → 解析 → 简历结构化 → ①筛查 → ②风险 → ③面试 → ④汇总(你在这) → 人工终判
```

你的模块是**收口**:赛题模块④要求「汇总候选人情况形成信息对比表、协助选人决策、合格候选人自动入库、分类标签管理、offer 弃权替补推送」。核心痛点「海量候选人复盘成本高」。

## 你的任务

构建 `src/talent_pool.py`,做三件事:

1. **汇总对比**:把多个候选人的 ① 筛查 + ② 风险结果,合并成一张对比表
2. **排序推荐**:按匹配度 + 风险综合排序,给出推荐/待定/不推荐
3. **人才库**:候选人带标签入库(`source` 区分"历史/外来",带备注标注)——这就是"双库 + 标注"的落地

## 输入(多个候选人的结果)

```json
{
  "candidates": [
    {"resume": {"name": "张三"}, "screening": {"overall": 85.0, "gaps": ["缺PCB"]}, "risk": {"risk_level": "低"}},
    {"resume": {"name": "李四"}, "screening": {"overall": 70.0, "gaps": []}, "risk": {"risk_level": "高"}}
  ]
}
```

## 输出(你要产出的 JSON)

```json
{
  "comparison": [
    {"name": "张三", "overall": 85.0, "risk_level": "低", "recommendation": "推荐"},
    {"name": "李四", "overall": 70.0, "risk_level": "高", "recommendation": "待定"}
  ],
  "ranking": ["张三", "李四"],
  "talent_pool": [
    {"name": "张三", "tags": ["嵌入式", "硕士"], "source": "incoming", "note": "技术扎实,可约复试"}
  ],
  "summary": "推荐张三进入复试;李四风险高,建议待定"
}
```

## 硬性要求

- **推荐要可解释**:每个候选人的 `recommendation` 要有依据(overall + risk 的组合规则,写清楚)
- **人才库带标注**:`talent_pool` 每个条目要 `tags`(分类标签)+ `source`(历史/外来)+ `note`(备注)——这是"共享人才表"的落点
- 排序规则用确定性逻辑(overall 降序,risk 高降权),别全甩给 LLM
- 小文件 + 不可变 + 中文注释
- 能独立运行:`python3 src/talent_pool.py`

## 完成标准

- [ ] `python3 src/talent_pool.py` 跑通,输出符合上面的 JSON
- [ ] 对比表 + 排序 + 人才库(带 tags/source/note)三件都有
- [ ] 推荐规则可解释(组合规则写清楚)
