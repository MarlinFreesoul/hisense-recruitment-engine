# -*- coding: utf-8 -*-
"""
生成 海信 AI 招聘智能体 工作流图 PDF
- 第 1 页：系统架构（四层）
- 第 2 页：招聘漏斗工作流（10 步闭环）
依赖：reportlab + 系统中文字体（微软雅黑 msyh.ttc / msyhbd.ttc）
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Flowable, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white, black

# ---------------- 字体注册 ----------------
FONT_PATH = r"C:/Windows/Fonts/msyh.ttc"
FONT_BOLD_PATH = r"C:/Windows/Fonts/msyhbd.ttc"
pdfmetrics.registerFont(TTFont("msyh", FONT_PATH, subfontIndex=0))
pdfmetrics.registerFont(TTFont("msyhbd", FONT_BOLD_PATH, subfontIndex=0))

# ---------------- 配色 ----------------
C_TITLE = HexColor("#0F4C81")   # 深蓝
C_ACCENT = HexColor("#1E88A8")  # 青
C_ARROW = HexColor("#5B7C99")
C_GRAY = HexColor("#5A6B7B")
C_BOX_A = HexColor("#EAF2FB")
C_BOX_B = HexColor("#E8F6F3")
C_BOX_STEP = HexColor("#F3F7FC")
C_BADGE = HexColor("#0F4C81")
C_LINE = HexColor("#B9C7D6")

# ---------------- 文本测量与换行 ----------------
def wrap_text(canv, text, font, size, max_width):
    canv.setFont(font, size)
    lines, cur = [], ""
    for ch in text:
        if canv.stringWidth(cur + ch, font, size) <= max_width:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines

def draw_text(canv, x, y, text, font, size, color, align="left"):
    canv.setFont(font, size)
    canv.setFillColor(color)
    if align == "center":
        canv.drawCentredString(x, y, text)
    elif align == "right":
        canv.drawRightString(x, y, text)
    else:
        canv.drawString(x, y, text)

def round_rect(canv, x, y, w, h, fill, stroke, radius=6, lw=1):
    canv.setFillColor(fill)
    canv.setStrokeColor(stroke)
    canv.setLineWidth(lw)
    canv.roundRect(x, y, w, h, radius, stroke=1, fill=1)

def v_arrow(canv, x, y_top, y_bottom, label, label_color=C_ARROW):
    """向下箭头：y_top 在上，y_bottom 在下（y_top > y_bottom）"""
    canv.setStrokeColor(C_ARROW)
    canv.setFillColor(C_ARROW)
    canv.setLineWidth(1.4)
    canv.line(x, y_top, x, y_bottom + 8)
    # 箭头头（朝下）
    canv.line(x - 4, y_bottom + 8, x, y_bottom)
    canv.line(x + 4, y_bottom + 8, x, y_bottom)
    if label:
        draw_text(canv, x + 10, y_bottom + 14, label, "msyh", 8.5, label_color)

# ---------------- 第 1 页：系统架构 ----------------
class ArchDiagram(Flowable):
    def __init__(self, width, height):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        canv = self.canv
        W = self.width
        H = self.height
        bx = 24
        bw = W - 48
        bh = 100
        gap = 30

        layers = [
            ("① 飞书多维表格", "数据 + HR 交互入口",
             "招聘需求表 · 简历库 · 评分结果表 · 权重配置表 · 面试记录表 · 招聘进度管理表 · 面试采集表", C_BOX_A),
            ("② FastAPI 接口层", "api/server.py · 端口 8000",
             "/parse_resume · /match · /jobs · /resumes · /results · /interview/questions · /interview/submit · /demo_data", C_BOX_B),
            ("③ 确定性代码引擎", "src/ · 可部署到任意机器",
             "resume_parser · llm_resume_parser(DeepSeek) · matcher_v2 · scoring(三态) · risk_filter · jd_generator · interview · talent · pipeline · feishu_client", C_BOX_A),
            ("④ 前端展示层", "展示 + 人工复核",
             "webapp/ Next.js 运营工作台（驾驶舱·岗位治理·人才匹配·AI初筛） · frontend/interview_form.html 静态 H5 面试采集表单", C_BOX_B),
        ]

        tops = []
        for i, (title, sub, comp, fill) in enumerate(layers):
            top = H - 18 - i * (bh + gap)
            round_rect(canv, bx, top - bh, bw, bh, fill, C_LINE)
            # 左侧色条
            canv.setFillColor(C_TITLE)
            canv.roundRect(bx, top - bh, 6, bh, 3, stroke=0, fill=1)
            draw_text(canv, bx + 18, top - 22, title, "msyhbd", 13, C_TITLE)
            draw_text(canv, bx + 18, top - 40, sub, "msyh", 9.5, C_GRAY)
            lines = wrap_text(canv, comp, "msyh", 9, bw - 40)
            ty = top - 58
            for ln in lines[:3]:
                draw_text(canv, bx + 18, ty, ln, "msyh", 9, HexColor("#33414F"))
                ty -= 13
            tops.append(top)

        # 连接箭头
        for i in range(len(layers) - 1):
            v_arrow(canv, bx + bw / 2, tops[i] - bh, tops[i + 1],
                    ["REST API（飞书开放平台）", "内部 import", "HTTP / CORS"][i])

# ---------------- 第 2 页：招聘漏斗 10 步 ----------------
STEPS = [
    ("① 岗位需求", "HR / 用人部门", "飞书「招聘需求表」录入 JD，或 clean_and_seed.py 填入真实制造岗"),
    ("② 简历入库", "HR", "简历进入「简历库」；非标简历经 LLM（DeepSeek）解析结构化写入"),
    ("③ 触发匹配", "系统", "python main.py --match 或 POST /match → matcher_v2.run_matching()"),
    ("④ 岗位族识别", "系统", "岗位名 match_job_family() 命中 6 大岗位族，未识别则跳过告警"),
    ("⑤ 加载模板 + 权重", "系统", "读 job_families_v2.json 岗位族模板，飞书「权重配置表」覆盖权重"),
    ("⑥ 打分 + 风险", "系统", "score_feishu_resume()：硬条件一票否决 + 软条件三态；risk_filter 识别风险"),
    ("⑦ 写回结果", "系统", "写回「评分结果表」Top N=5；A/B 级生成面试题；更新进度表"),
    ("⑧ 前端展示 + 人工复核", "HR", "工作台查看匹配证据/风险点，安排面试；H5 表单走初筛"),
    ("⑨ 面试采集", "候选人", "H5 表单采集倒班/到岗/证书/稳定性等硬指标，写入「面试采集表」"),
    ("⑩ 人工终审 + 决策", "HR", "AI 仅辅助判断，不自动录用/淘汰；敏感信息不进入筛选"),
]

class FunnelDiagram(Flowable):
    def __init__(self, width, height):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        canv = self.canv
        W = self.width
        H = self.height
        bx = 24
        bw = W - 48
        bh = 56
        gap = 14

        for i, (title, role, action) in enumerate(STEPS):
            top = H - 16 - i * (bh + gap)
            fill = C_BOX_STEP if i % 2 == 0 else HexColor("#EFF4FA")
            round_rect(canv, bx, top - bh, bw, bh, fill, C_LINE)
            # 数字徽章
            cx = bx + 24
            cy = top - bh / 2
            canv.setFillColor(C_BADGE)
            canv.circle(cx, cy, 15, stroke=0, fill=1)
            draw_text(canv, cx, cy - 4.5, str(i + 1), "msyhbd", 13, white, align="center")
            # 文本
            tx = bx + 48
            draw_text(canv, tx, top - 16, title, "msyhbd", 11.5, C_TITLE)
            draw_text(canv, tx, top - 33, "角色：" + role, "msyh", 8.5, C_GRAY)
            draw_text(canv, tx, top - 47, action, "msyh", 9, HexColor("#33414F"))
            # 步骤间箭头
            if i < len(STEPS) - 1:
                v_arrow(canv, bx + bw - 16, top - bh, top - (bh + gap), "")

# ---------------- 文档与页码 ----------------
def footer(canv, doc):
    canv.saveState()
    canv.setFont("msyh", 8)
    canv.setFillColor(C_GRAY)
    canv.drawString(40, 22, "海信 AI 招聘智能体 · 工作流图  (Hisense HireAI)")
    canv.drawRightString(A4[0] - 40, 22, "第 %d 页 / 共 2 页" % doc.page)
    canv.setStrokeColor(C_LINE)
    canv.setLineWidth(0.5)
    canv.line(40, 30, A4[0] - 40, 30)
    canv.restoreState()

def build():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflow.pdf")
    doc = BaseDocTemplate(out, pagesize=A4,
                          leftMargin=40, rightMargin=40,
                          topMargin=46, bottomMargin=40,
                          title="海信 AI 招聘智能体 工作流图")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=footer)])

    title_style = ParagraphStyle("t", fontName="msyhbd", fontSize=16, textColor=C_TITLE,
                                  spaceAfter=4, leading=20)
    sub_style = ParagraphStyle("s", fontName="msyh", fontSize=9.5, textColor=C_GRAY,
                               spaceAfter=10, leading=13)

    from reportlab.platypus import PageBreak
    flow = []
    flow.append(Paragraph("海信 AI 招聘智能体 · 系统架构", title_style))
    flow.append(Paragraph("四层结构：飞书（数据+交互）→ FastAPI（接口）→ 确定性代码引擎（算法）→ 前端（展示+复核）", sub_style))
    flow.append(ArchDiagram(doc.width, 500))
    flow.append(PageBreak())
    flow.append(Paragraph("招聘漏斗工作流 · 10 步闭环", title_style))
    flow.append(Paragraph("从岗位发布到人工终审：AI 辅助筛选与风险识别，最终决策权始终在 HR", sub_style))
    flow.append(FunnelDiagram(doc.width, 690))
    doc.build(flow)
    print("已生成:", out)

if __name__ == "__main__":
    build()
