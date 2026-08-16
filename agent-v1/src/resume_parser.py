"""简历 PDF 解析节点(OCR)

Demo 演示用:把投递进来的 PDF 简历自动识别成文本,交给下游「简历筛选」模块。

策略:文本优先(PyMuPDF 直接抽取)→ 文本量不足判定为扫描件 → RapidOCR 兜底。

用法:
    from resume_parser import parse_resume

    result = parse_resume("resume.pdf")
    print(result.source)      # 'text' | 'ocr' | 'empty'
    print(result.raw_text)    # 识别出的全文
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import fitz  # PyMuPDF

# 扫描件判定阈值:每页可抽取文本少于该字符数,视为扫描/图片型 PDF
MIN_TEXT_CHARS_PER_PAGE = 30
# 渲染页面的分辨率(DPI),越高 OCR 越准、越慢
OCR_DPI = 200


@dataclass
class ParsedResume:
    """简历解析节点的输出契约(节点化 = 干净的输入输出)。"""

    raw_text: str
    source: str  # 'text' | 'ocr' | 'empty'
    page_count: int
    text_length: int
    pdf_path: str
    ocr_confidence: float | None = None

    def to_dict(self) -> dict:
        return {
            "raw_text": self.raw_text,
            "source": self.source,
            "page_count": self.page_count,
            "text_length": self.text_length,
            "pdf_path": self.pdf_path,
            "ocr_confidence": self.ocr_confidence,
        }


def _extract_text(pdf_path: str) -> str:
    """PyMuPDF 直接抽取 PDF 内嵌文本(文本型 PDF 零成本秒出)。"""
    with fitz.open(pdf_path) as doc:
        return "\n".join(page.get_text() for page in doc)


def _page_count(pdf_path: str) -> int:
    with fitz.open(pdf_path) as doc:
        return doc.page_count


def _needs_ocr(text: str, page_count: int) -> bool:
    """文本量过少 → 判定为扫描/图片型 PDF,需要 OCR。"""
    return len(text.strip()) < page_count * MIN_TEXT_CHARS_PER_PAGE


@lru_cache(maxsize=1)
def _get_ocr_engine():
    """懒加载 RapidOCR 引擎,复用避免每次重载模型。"""
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _ocr_pdf(pdf_path: str) -> tuple[str, float]:
    """对每个页面做 OCR,返回 (文本, 平均置信度)。"""
    import numpy as np

    engine = _get_ocr_engine()
    page_texts: list[str] = []
    scores: list[float] = []

    with fitz.open(pdf_path) as doc:
        for page in doc:
            # alpha=False 强制 RGB,避免 RGBA 4 通道让 OCR 报错
            pix = page.get_pixmap(dpi=OCR_DPI, alpha=False)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            result, _ = engine(img)
            if result:
                page_texts.append("\n".join(item[1] for item in result))
                scores.extend(float(item[2]) for item in result)

    text = "\n".join(page_texts)
    confidence = sum(scores) / len(scores) if scores else 0.0
    return text, confidence


def parse_resume(pdf_path: str | Path) -> ParsedResume:
    """简历解析节点入口:PDF → 文本(文本优先,OCR 兜底)。"""
    pdf_path = str(pdf_path)
    pages = _page_count(pdf_path)
    text = _extract_text(pdf_path)

    # 完全没文本,或文本量过少 → 扫描件,走 OCR
    if not text.strip() or _needs_ocr(text, pages):
        ocr_text, confidence = _ocr_pdf(pdf_path)
        return ParsedResume(
            raw_text=ocr_text,
            source="ocr" if ocr_text.strip() else "empty",
            page_count=pages,
            text_length=len(ocr_text),
            pdf_path=pdf_path,
            ocr_confidence=confidence,
        )

    # 文本型 PDF,直接用抽取结果
    return ParsedResume(
        raw_text=text,
        source="text",
        page_count=pages,
        text_length=len(text),
        pdf_path=pdf_path,
    )


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "resume.pdf"
    result = parse_resume(path)
    print(
        f"source={result.source}  pages={result.page_count}  "
        f"chars={result.text_length}  conf={result.ocr_confidence}"
    )
    print("---- 文本预览 ----")
    print(result.raw_text[:2000])
