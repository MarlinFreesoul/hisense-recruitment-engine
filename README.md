# 海信 AI 招聘智能体 · 后端引擎 + 前端工作台 + 制造业招聘知识库

> **不是通用 HR SaaS，而是把海信容声真实招聘岗位沉淀成「制造业招聘知识库」**——让 HR 在重复岗位筛选和面试题准备上显著降本增效。

**一句话**：JD 发出去收 1000 份简历，系统几分钟内筛出 top 8~9 人，给出「为什么是这几个人」的可解释评分报告，并为通过者生成面试采集问卷。

## 核心亮点

- ✅ **确定性打分引擎**：同一份简历在任何机器跑出同一个分数，每个分数追得到规则行（三态：满足/不满足/未知）
- ✅ **6 大岗位族 JD 模板** + 两套匹配权重（一线岗 vs 专业岗自动切换）
- ✅ **权重飞书化**：HR 在飞书「权重配置表」里改权重，评分实时生效，每一分可审计
- ✅ **LLM 简历解析**（DeepSeek）：非标简历（口语化/字段缺失）也能正确结构化
- ✅ **辅助面试采集**：H5 表单固定发问核心指标（倒班/到岗/证书有效期），零 LLM 对话
- ✅ **权威调研报告**：423 条真实岗位数据 + 信源可及性评分

## 目录结构

```
hisense-recruitment/
├── main.py                    # 后端 CLI 入口（持续运行服务）
├── config.py                  # 统一配置（.env 加载，凭证不入库）
├── api/server.py              # FastAPI 后端（前端/同事调用）
├── src/                       # 算法引擎
│   ├── scoring.py             # 确定性打分引擎（三态）
│   ├── matcher_v2.py          # 整合评分主流程（读飞书→评分→写回）
│   ├── llm_resume_parser.py   # LLM 简历解析（DeepSeek）
│   ├── interview_collect.py   # 辅助面试核心问题采集
│   ├── interview.py / talent.py  # 面试题 + 人才评价
│   └── risk_filter.py / jd_generator.py / resume_parser.py / feishu_client.py
├── data/                      # 知识库（job_families / major_mapping / question_bank）
├── frontend/                  # H5 面试采集表单（静态）
├── webapp/                    # ★ vinext 前端工作台（React，同事开发）
├── docs/                      # 调研报告 + 系统架构
└── scripts/                   # 数据初始化脚本
```

## 快速开始

### 后端（FastAPI，端口 8000）

```bash
pip install -r requirements.txt
cp .env.example .env        # 填飞书凭证 + DeepSeek key
python main.py              # 启动 API 服务，访问 http://localhost:8000/docs
```

### 前端（vinext，端口 3000）

```bash
cd webapp
npm install
npm run dev -- --hostname 0.0.0.0   # 访问 http://localhost:3000
```

### 前后端打通

- 后端 `localhost:8000` 已配 CORS，前端跨域调用
- H5 面试表单：`http://localhost:3000/interview_form.html?candidate=<record_id>`（调用后端 `/interview/questions` + `/interview/submit`）

## 核心 API

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/parse_resume` | 简历文本 → 结构化字段（LLM） |
| POST | `/match` | 触发匹配评分，写回飞书 |
| GET | `/jobs` `/resumes` `/results` | 读飞书数据 |
| GET | `/interview/questions` | 生成核心采集问题 |
| POST | `/interview/submit` | 采集回复写飞书 |

## 打分逻辑（确定性、三态、可调权重）

- **硬条件**：布尔规则一票否决（学历/倒班/到岗）
- **软条件**：确定性评分函数 × 权重；字段「缺失」标未知（剔除不扣分），「不满足」才扣分
- **权重**：飞书「权重配置表」可调，实时生效

## 已知限制（诚实标注）

1. **简历解析**：规则版对非标简历鲁棒性有限，结构化走 `llm_resume_parser.py`（DeepSeek）
2. **评分权重**：默认值需 HR 用真实批量简历 + 录用标注校准
3. **飞书/DeepSeek**：需真实凭证（`.env` 配置）
4. **研发岗**：样本少，题库暂并入工艺设备类
