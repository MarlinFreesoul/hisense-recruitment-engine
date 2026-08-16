# 简历 PDF 解析节点(OCR)设计

## 问题

简历以 PDF 形式投递,招聘智能体 Demo 需要先自动识别出文字,再交给下游「简历筛选」模块。本节点解决「PDF → 文本」这一段。

## 核心判断:大多数简历 PDF 其实不需要 OCR

简历 PDF 分两种:

| 类型 | 来源 | 处理方式 |
|---|---|---|
| **文本型**(约 80%) | Word/WPS/在线简历平台导出 | 文字已内嵌,直接抽取 |
| **扫描/图片型** | 纸质简历扫描、拍照转 PDF | 页面是图片,必须 OCR |

关键策略是 **「文本优先,OCR 兜底」**——先尝试直接抽取文本,只有文本量不足时才走 OCR。上来就 OCR 会浪费 80% 的时间在无意义的识别上,又慢又可能引入错字。

## 方案对比

| 方案 | 中文 | 成本 | 部署 | 适用 |
|---|---|---|---|---|
| **PyMuPDF 文本抽取** | n/a(直接抽取) | 免费 | 极轻 | 文本型 PDF |
| **RapidOCR** | 强 | 免费 | 轻(onnxruntime) | 扫描 PDF |
| PaddleOCR | 强 | 免费 | 重(PaddlePaddle 数百 MB) | 扫描 PDF |
| Tesseract | 弱(中文差) | 免费 | 轻 | ❌ 不推荐中文 |
| 云 OCR(百度/腾讯/火山) | 强 | 付费 | API | 预算充足 |
| 多模态 LLM(通义千问-VL/GPT-4o) | 强 | 付费 | API | 想一步到位结构化 |

## 推荐方案

**PyMuPDF(文本优先)→ 文本量不足时 RapidOCR 兜底 → 下游 LLM 结构化(DeepSeek)**

理由:

1. PyMuPDF 已装好,文本型简历零成本秒出。
2. RapidOCR 用 PaddleOCR 同款中文模型、但跑在 onnxruntime 上,免装数百 MB 的 PaddlePaddle,hackathon 时间友好。
3. 全程免费本地,契合「低成本」约束(不碰云 OCR / 多模态 LLM)。

## 节点架构与位置

```
[PDF 简历] → ① 简历解析节点(本节点) → 原始文本 → ② LLM 结构化节点 → 结构化简历 JSON → ③ 简历筛选/匹配节点
                ├ 文本抽取(PyMuPDF)
                ├ 判定是否扫描件(文本量阈值)
                └ OCR 兜底(RapidOCR)
```

**输入/输出契约**(「节点化」= 干净的输入输出,可插拔、可编排):

- 输入:`pdf_path`(str)
- 输出:`ParsedResume { raw_text, source(text|ocr|empty), page_count, text_length, ocr_confidence }`

节点无状态、可复用,后续可包成 n8n / Coze / Dify 的工作流节点,或直接作为 Python pipeline 的一环。

## 安装

```bash
pip install pymupdf rapidocr-onnxruntime   # pymupdf 已装,只需补 rapidocr
```

## 为什么不选

- **PaddleOCR**:要装 PaddlePaddle(数百 MB),版本易冲突,hackathon 时间不划算。
- **云 OCR / 多模态 LLM**:要花钱,且 DeepSeek 无视觉能力;「本地 OCR + 便宜 LLM」性价比更高。
- **Tesseract**:中文识别质量差,排版密集的中文简历会漏字错字。

## 待办(下一节点)

OCR 只是第一环。下一步接「LLM 结构化节点」:把原始文本抽成
`{姓名, 学历, 学校, 专业, 工作经历[], 技能[], 电话}` 等字段,再喂给匹配评分。

## 测试

```bash
# 文本型 PDF(应走 source=text)
python3 src/resume_parser.py 某份Word导出的简历.pdf

# 扫描型 PDF(应走 source=ocr,需先装 rapidocr)
python3 src/resume_parser.py 某份扫描简历.pdf
```
