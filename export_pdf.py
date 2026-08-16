# -*- coding: utf-8 -*-
"""
将 项目说明.md 转换为 PDF（reportlab + 系统字体 微软雅黑 msyh）。
微软雅黑覆盖极广（中文 / 方框字符 / 箭头 / 圆圈数字 / 各类符号），
仅 ✅/✓ 等 emoji 缺失，已在 sanitize() 中兜底替换。
用法: python export_pdf.py
"""
import re
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
    Preformatted, HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "项目说明.md")
OUT = os.path.join(BASE, "项目说明.pdf")

# ---- 注册中文字体（微软雅黑，覆盖最广）----
REG = r"C:\Windows\Fonts\msyh.ttc"      # 常规
BOLD = r"C:\Windows\Fonts\msyhbd.ttc"   # 粗体
pdfmetrics.registerFont(TTFont("YaHei", REG, subfontIndex=0))
pdfmetrics.registerFont(TTFont("YaHei-Bold", BOLD, subfontIndex=0))
pdfmetrics.registerFontFamily("YaHei", normal="YaHei", bold="YaHei-Bold",
                              italic="YaHei", boldItalic="YaHei-Bold")
CN = "YaHei"

# 字体缺失字符的兜底（仅 ✅/✓ 等 emoji 缺失）
_ya_cg = pdfmetrics.getFont("YaHei").face.charToGlyph
_CODEPOINTS = set(int(k) for k in _ya_cg.keys())
_REPL = {"\u2705": "[OK]", "\u2713": "[OK]"}


def sanitize(s: str) -> str:
    """把字体里没有的字符替换掉，杜绝 PDF 出现 ■ 乱码。"""
    out = []
    for ch in s:
        cp = ord(ch)
        if cp < 128 or cp in _CODEPOINTS:
            out.append(ch)
        else:
            out.append(_REPL.get(ch, " "))
    return "".join(out)


# ---- 样式 ----
styles = getSampleStyleSheet()
def mk(name, **kw):
    base = dict(fontName=CN, leading=14, spaceAfter=6, textColor=colors.HexColor("#1a1a1a"))
    base.update(kw)
    return ParagraphStyle(name, **base)

H1 = mk("H1", fontSize=20, leading=26, spaceBefore=14, spaceAfter=10, textColor=colors.HexColor("#0b4f9c"))
H2 = mk("H2", fontSize=15, leading=20, spaceBefore=12, spaceAfter=7, textColor=colors.HexColor("#0b4f9c"))
H3 = mk("H3", fontSize=12.5, leading=17, spaceBefore=9, spaceAfter=5, textColor=colors.HexColor("#1f6feb"))
H4 = mk("H4", fontSize=11, leading=15, spaceBefore=7, spaceAfter=4, textColor=colors.HexColor("#333333"))
BODY = mk("BODY", fontSize=10, leading=15, alignment=TA_LEFT)
BULLET = mk("BULLET", fontSize=10, leading=15, leftIndent=14, bulletIndent=4, spaceAfter=3)
# 代码块改用雅黑，确保方框字符（┌│─▼ 等）与箭头正常渲染
CODE = ParagraphStyle("CODE", fontName=CN, fontSize=8.5, leading=12,
                      backColor=colors.HexColor("#f4f4f5"), borderColor=colors.HexColor("#d0d0d5"),
                      borderWidth=0.5, borderPadding=6, textColor=colors.HexColor("#222222"),
                      spaceBefore=4, spaceAfter=8)
QUOTE = mk("QUOTE", fontSize=10, leading=15, leftIndent=12, textColor=colors.HexColor("#555555"),
           backColor=colors.HexColor("#f0f6ff"), borderColor=colors.HexColor("#cfe0ff"),
           borderWidth=0, borderPadding=6, spaceBefore=2, spaceAfter=8)
CELL = mk("CELL", fontSize=8.5, leading=11)
CELLH = mk("CELLH", fontSize=8.5, leading=11, textColor=colors.white, fontName=CN)


def inline(s: str) -> str:
    """转义 XML 并支持 **粗体** 与 `行内代码`。"""
    s = sanitize(s)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    # 行内代码：纯 ASCII 用 Courier 保持等宽；含中文则改用雅黑，避免中文变 ■
    def _code(m):
        txt = m.group(1)
        face = "Courier" if all(ord(c) < 128 for c in txt) else CN
        return '<font face="%s">%s</font>' % (face, txt)
    s = re.sub(r"`([^`]+?)`", _code, s)
    return s


def parse_row(line: str):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def build_table(rows):
    header = parse_row(rows[0])
    data = [header]
    for r in rows[2:]:  # 跳过分隔行 rows[1]
        data.append(parse_row(r))
    ncol = len(header)
    table_data = []
    for ri, row in enumerate(data):
        cells = []
        for ci in range(ncol):
            txt = row[ci] if ci < len(row) else ""
            st = CELLH if ri == 0 else CELL
            cells.append(Paragraph(inline(txt), st))
        table_data.append(cells)
    # 列宽：按比例分配可用宽度
    avail = A4[0] - 3.6 * cm
    maxlen = [0] * ncol
    for row in data:
        for ci in range(ncol):
            txt = row[ci] if ci < len(row) else ""
            maxlen[ci] = max(maxlen[ci], sum(1.8 if ord(c) > 255 else 1 for c in txt))
    total = sum(maxlen) or 1
    widths = [max(1.2 * cm, avail * (ml / total)) for ml in maxlen]
    t = Table(table_data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b4f9c")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b0b0b8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6fb")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def render(md_text: str):
    lines = md_text.split("\n")
    story = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        # 空行
        if stripped == "":
            i += 1
            continue

        # 代码块
        if stripped.startswith("```"):
            i += 1
            code = []
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1  # 跳过结束 ```
            if code:
                story.append(Preformatted(sanitize("\n".join(code)), CODE))
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            txt = inline(m.group(2))
            style = {1: H1, 2: H2, 3: H3, 4: H4, 5: H4, 6: H4}[level]
            story.append(Paragraph(txt, style))
            i += 1
            continue

        # 分隔线
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            story.append(HRFlowable(width="100%", thickness=0.6,
                                    color=colors.HexColor("#cccccc"), spaceBefore=6, spaceAfter=8))
            i += 1
            continue

        # 引用块
        if stripped.startswith(">"):
            quote = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(re.sub(r"^>\s?", "", lines[i].strip()))
                i += 1
            story.append(Paragraph(inline(" ".join(quote)), QUOTE))
            continue

        # 表格（当前行以 | 开头，且后续存在分隔行）
        if stripped.startswith("|") and i + 1 < n and re.match(r"^\s*\|?[\s:\-|]+\|?\s*$", lines[i + 1]):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            story.append(build_table(rows))
            story.append(Spacer(1, 4))
            continue

        # 无序列表
        if re.match(r"^[-*+]\s+", stripped):
            items = []
            while i < n and re.match(r"^[-*+]\s+", lines[i].strip()):
                item = re.sub(r"^[-*+]\s+", "", lines[i].strip())
                items.append(item)
                i += 1
            for it in items:
                story.append(Paragraph(inline(it), BULLET, bulletText="•"))
            continue

        # 普通段落（合并连续非特殊行）
        para = [stripped]
        i += 1
        while i < n and lines[i].strip() != "" \
                and not lines[i].strip().startswith("#") \
                and not lines[i].strip().startswith(">") \
                and not lines[i].strip().startswith("|") \
                and not lines[i].strip().startswith("```") \
                and not re.match(r"^[-*+]\s+", lines[i].strip()) \
                and not re.match(r"^(-{3,}|\*{3,}|_{3,})$", lines[i].strip()):
            para.append(lines[i].strip())
            i += 1
        story.append(Paragraph(inline(" ".join(para)), BODY))
    return story


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(CN, 8)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawString(2 * cm, 1.1 * cm, sanitize("海信 AI 招聘智能体 · 项目说明"))
    canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, "第 %d 页" % doc.page)
    canvas.restoreState()


def main():
    with open(SRC, encoding="utf-8") as f:
        md = f.read()
    story = render(md)
    doc = BaseDocTemplate(OUT, pagesize=A4,
                          leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                          topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                          title="海信 AI 招聘智能体 · 项目说明",
                          author="WorkBuddy")
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=footer)])
    doc.build(story)
    print("生成:", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
