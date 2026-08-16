# MAPBOARD · 地图板（项目溯源索引）

> 项目：海信 AI 招聘智能体（顺德AI黑客松 · 企业命题赛道）
> 方法论：**Spec Kit Lite**（spec-first 但轻量 = Spec Kit 官方 shorter path，砍掉 clarify/analyze/constitution 重仪式）
> 命名规范：报告名 = `R.T-主题.md`，**R = 对话轮次，T = 该轮报告序号**
> 维护角色：**Spec Kit Lite 专家**（`spec-kit-lite-expert`）

---

## 一、对话轮次总览（每轮一句话总结）

| 版本 | 轮次 | 主题 | 一句话总结（主题 + 最关键动作） | 关键动作 |
|------|:---:|------|------|------|
| **1.1** | R1 | 黑客松专家团盘点 | 激活女娲，盘点出「顺德黑客松备战委员会」这个现成专家团 | 确认现有虚拟战略委员会 |
| **2.1** | R2 | 海信赛题六大问题调研 | 读取海信赛题，Metaso+Exa 双引擎并行调研六大问题并建立信源评分 | 双引擎调研 + 信源评分 |
| **2.2** | R2 | 信源可信度自证 | 逐条审计 31 个信源的评分与三角验证，诚实披露四大局限 | 信源自证 |
| **3.1** | R3 | Spec Kit 适用性评估 | 把三份产出版本化提交 GitHub，判定 Spec Kit「可行非最优」并给加权评分 | 版本化提交 + Spec Kit 判定 |
| **4.1** | R4 | Spec Kit Lite 权威描述 | 求证「Spec Kit Lite」无官方产品，锁定官方 shorter path + OpenSpec 为权威锚点 | 创建方法论专家 + 溯源体系 |

## 二、报告四要素覆盖矩阵

| 报告 | ①信源评分 | ②权重矩阵 | ③对抗辩证矩阵 | ④Promptx 角色分工 |
|------|:---:|:---:|:---:|:---:|
| 1.1 | ✅ | — | — | ✅ |
| 2.1 | ✅ | — | ✅ | ✅ |
| 2.2 | ✅ | — | — | — |
| 3.1 | ✅ | ✅ | ✅ | ✅ |
| 4.1 | ✅ | ✅ | ✅ | ✅ |

> 四要素定义见 [`reports/_TEMPLATE.md`](./reports/_TEMPLATE.md)。「—」表示该报告本轮未含此要素，后续按模板补齐。

## 三、文件清单（溯源）

| 路径 | 说明 | 来源轮次 |
|------|------|:---:|
| `MAPBOARD.md` | 地图板（本文件，唯一溯源入口） | R4 |
| `reports/_TEMPLATE.md` | 报告四要素模板 | R4 |
| `reports/1.1-hackathon-committee.md` | 第一轮：委员会盘点 | R1 |
| `reports/2.1-six-questions-research.md` | 第二轮：六大问题调研 | R2 |
| `reports/2.2-source-credibility-audit.md` | 第二轮：信源自证 | R2 |
| `reports/3.1-spec-kit-evaluation.md` | 第三轮：Spec Kit 评估 | R3 |
| `reports/4.1-spec-kit-lite-authoritative-description.md` | 第四轮：Spec Kit Lite 权威描述 | R4 |
| `docs/hisense-ai-recruitment-agent.md` | 赛题原始资料（源材料，非生成物） | R2 |
| `.specify/` | Spec Kit 脚手架（保留，不跑全量流程） | R3 前 |

## 四、溯源规则

1. **每个文件必有其轮次**：任何 `reports/` 下的报告，文件名首段 `R.T` 即其轮次。
2. **每轮必有一句话总结**：见上表「一句话总结」列，格式 = 主题 + 关键动作。
3. **新增报告三步走**：①在报告名写 `R.T` ②按 `_TEMPLATE.md` 填四要素 ③在本表登记一行。
4. **改写不删历史**：内容迭代走 git 版本提交，不改写已登记的历史轮次总结。
