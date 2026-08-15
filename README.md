# 海信 AI 招聘智能体 · 算法引擎 + 制造业招聘知识库

> **不是通用 HR SaaS，而是把海信容声真实招聘岗位沉淀成「制造业招聘知识库」**——让 HR 在重复岗位筛选和面试题准备上显著降本增效。

**一句话**：JD 发出去收 1000 份简历，这个引擎几分钟内筛出 top 8~9 人，并给出「为什么是这几个人」的可解释评分报告。

## 核心亮点

- ✅ **确定性打分引擎**：同一份简历在任何机器跑出同一个分数，每个分数追得到规则行
- ✅ **6 大岗位族 JD 模板** + 两套匹配权重（一线岗 vs 专业岗自动切换）
- ✅ **岗位-专业对应表**：简历出现训练数据没见过的专业，也能判岗位对口
- ✅ **权威调研报告**：423 条真实岗位数据 + 信源可及性评分

## 30 秒跑起来

```bash
pip install -r requirements.txt
python main.py --resume sample_resume.json --job firstline
# → 输出「匹配度 98 分（A 级）→ 通过筛选 → 推送 HR 初面」的可解释评分报告
```

## 目录结构

```
hisense-recruitment/
├── main.py                    # CLI 入口
├── requirements.txt           # 依赖
├── sample_resume.json         # 结构化简历样本（RESUME-001）
├── job_families_v2.json       # 6 大岗位族图谱 + JD 模板 + 权重（单一数据源）
├── major_job_mapping.json     # 岗位-专业对应表（泛化能力底座）
├── interview_question_bank.json  # 5 类结构化面试题库
├── src/
│   ├── scoring.py             # 确定性打分引擎（可复现）
│   ├── jd_generator.py        # JD 生成（模板渲染 + 参数）
│   ├── risk_filter.py         # 风险识别（确定性规则）
│   ├── resume_parser.py       # 简历解析（规则兜底 + LLM 接口）
│   ├── pipeline.py            # 漏斗编排
│   └── feishu_client.py       # 飞书接入（多维表格 + 机器人）
└── docs/
    ├── 调研报告.md            # 权威调研报告
    └── 系统架构.md            # 架构 + 流程图
```

## 快速开始

```bash
pip install -r requirements.txt

# 方式一：结构化简历 JSON 直接进漏斗（推荐，简历结构化由 data 角色/LLM 产出）
python main.py --resume sample_resume.json --job firstline

# 方式二：简历 PDF（规则兜底 + LLM 接口）
python main.py --resume 简历.pdf --job firstline
```

岗位族 key：`firstline`（一线）/ `production-management`（管培）/ `process-equipment`（工艺设备）/ `quality`（质量）/ `procurement-logistics`（采购物流）/ `rnd-engineering`（研发）。

## 打分逻辑（确定性、可复现）

- **硬条件**：布尔规则，一票否决（年龄/学历/到岗/倒班）。
- **软条件**：每个维度一个**确定性评分函数** × 权重，映射 0-100。
- 同一份结构化简历，在任何机器上跑出同一个分数（无随机、无 LLM 临场打分）。
- 权重与评分函数是**配置 + 代码**，不是模型发挥；LLM 仅在「专业对口/职位对口」语义判断介入。

## 飞书接入

```bash
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="xxx"
export FEISHU_BOT_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"

python main.py --resume sample_resume.json --job firstline --feishu
```

`feishu_client.py` 提供多维表格写入 + 群机器人推送，需在飞书开放平台创建应用并开通「多维表格」权限。

## 已知限制（诚实标注）

1. **简历解析**：`resume_parser.py` 的规则版对真实简历多样性鲁棒性有限，结构化应走 `llm_extract` 接口接 LLM（`shunde-data` 的职责）。
2. **评分权重**：当前权重为「招聘实践 + 数据分布」的默认值，需 HR 用真实批量简历 + 录用标注校准。
3. **飞书**：需真实应用凭证才能连上，代码为标准 API 封装。
4. **研发岗**：样本少，题库暂并入工艺设备类，待数据补齐单列。
