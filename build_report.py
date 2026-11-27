#!/usr/bin/env python3
"""Build the Lab3 PDF report with a compact, reproducible ReportLab layout."""

from __future__ import annotations

import html
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "Lab3_AttackLab_Report.md"
OUTPUT = ROOT / "Lab3_AttackLab_Report.pdf"

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

PAGE_W, PAGE_H = A4
NAVY = colors.HexColor("#16324F")
BLUE = colors.HexColor("#2A6F97")
LIGHT_BLUE = colors.HexColor("#EAF3F8")
LIGHT_GREY = colors.HexColor("#F3F5F7")
MID_GREY = colors.HexColor("#6B7785")
INK = colors.HexColor("#222B33")

styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        "CnBody",
        fontName="STSong-Light",
        fontSize=10.0,
        leading=15.8,
        textColor=INK,
        spaceAfter=6,
        wordWrap="CJK",
    )
)
styles.add(
    ParagraphStyle(
        "CnTitle",
        fontName="STSong-Light",
        fontSize=23,
        leading=32,
        textColor=NAVY,
        alignment=TA_CENTER,
        spaceAfter=16,
    )
)
styles.add(
    ParagraphStyle(
        "CnSubtitle",
        fontName="STSong-Light",
        fontSize=10.5,
        leading=17,
        textColor=MID_GREY,
        alignment=TA_CENTER,
        spaceAfter=5,
    )
)
styles.add(
    ParagraphStyle(
        "CnH1",
        fontName="STSong-Light",
        fontSize=16.5,
        leading=23,
        textColor=NAVY,
        spaceBefore=12,
        spaceAfter=9,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        "CnH2",
        fontName="STSong-Light",
        fontSize=12.6,
        leading=19,
        textColor=BLUE,
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        "CnBullet",
        parent=styles["CnBody"],
        leftIndent=16,
        firstLineIndent=-9,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        "CnCode",
        fontName="Courier",
        fontSize=8.2,
        leading=11.4,
        textColor=colors.HexColor("#1A2732"),
        leftIndent=10,
        rightIndent=10,
        spaceBefore=5,
        spaceAfter=8,
        backColor=LIGHT_GREY,
        borderColor=colors.HexColor("#D8DEE5"),
        borderWidth=0.5,
        borderPadding=7,
    )
)
styles.add(
    ParagraphStyle(
        "CnCodeMixed",
        parent=styles["CnCode"],
        fontName="STSong-Light",
        fontSize=9.1,
        leading=13.2,
    )
)
styles.add(
    ParagraphStyle(
        "CnTable",
        fontName="STSong-Light",
        fontSize=8.6,
        leading=12.2,
        textColor=INK,
        wordWrap="CJK",
    )
)


def inline_markup(text: str) -> str:
    text = html.escape(text)
    parts = text.split("`")
    for i in range(1, len(parts), 2):
        parts[i] = f'<font name="Courier" color="#16324F">{parts[i]}</font>'
    text = "".join(parts)
    text = text.replace("**", "")
    return text


def page_decor(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D9E2E8"))
    canvas.setLineWidth(0.5)
    canvas.line(20 * mm, 17 * mm, PAGE_W - 20 * mm, 17 * mm)
    canvas.setFont("STSong-Light", 8)
    canvas.setFillColor(MID_GREY)
    canvas.drawString(20 * mm, 11 * mm, "CS10005.02  Lab3: AttackLab")
    canvas.drawRightString(PAGE_W - 20 * mm, 11 * mm, f"{doc.page}")
    canvas.restoreState()


def add_table(rows: list[list[str]]) -> Table:
    data = []
    for r_index, row in enumerate(rows):
        style = ParagraphStyle(
            "HeaderCell" if r_index == 0 else "TableCell",
            parent=styles["CnTable"],
            textColor=colors.white if r_index == 0 else INK,
            fontName="STSong-Light",
        )
        rendered = []
        for cell in row:
            if r_index == 0:
                rendered.append(Paragraph(html.escape(cell).replace("`", ""), style))
            else:
                rendered.append(Paragraph(inline_markup(cell), style))
        data.append(rendered)
    content_width = PAGE_W - 40 * mm
    fractions = [1.0] * len(rows[0])
    if len(rows[0]) == 2:
        fractions = [0.24, 0.76]
    elif len(rows[0]) == 3:
        fractions = [0.20, 0.30, 0.50]
    elif len(rows[0]) == 4:
        fractions = [0.20, 0.24, 0.34, 0.22]
    widths = [content_width * fraction for fraction in fractions]
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#CBD5DD")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BLUE]),
            ]
        )
    )
    return table


def parse_markdown(markdown: str) -> list:
    lines = markdown.splitlines()
    flow = []
    paragraph: list[str] = []
    table_rows: list[list[str]] = []
    code_lines: list[str] = []
    in_code = False
    title_done = False
    subtitle_lines: list[str] = []

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            text = " ".join(x.strip() for x in paragraph)
            flow.append(Paragraph(inline_markup(text), styles["CnBody"]))
            paragraph = []

    def flush_table():
        nonlocal table_rows
        if table_rows:
            flow.append(Spacer(1, 3))
            flow.append(add_table(table_rows))
            flow.append(Spacer(1, 7))
            table_rows = []

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("```"):
            flush_paragraph()
            flush_table()
            if in_code:
                text = "\n".join(code_lines)
                code_style = (
                    styles["CnCodeMixed"]
                    if any(ord(ch) > 127 for ch in text)
                    else styles["CnCode"]
                )
                flow.append(Preformatted(text, code_style, maxLineLength=100))
                code_lines = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_lines.append(line)
            i += 1
            continue
        if line.startswith("# "):
            if not title_done:
                flow.append(Paragraph(inline_markup(line[2:]), styles["CnTitle"]))
                title_done = True
            else:
                flow.append(Paragraph(inline_markup(line[2:]), styles["CnH1"]))
            flush_paragraph()
            i += 1
            continue
        if line.startswith("## "):
            flush_paragraph()
            flush_table()
            flow.append(Paragraph(inline_markup(line[3:]), styles["CnH1"]))
            i += 1
            continue
        if line.startswith("### "):
            flush_paragraph()
            flush_table()
            flow.append(Paragraph(inline_markup(line[4:]), styles["CnH2"]))
            i += 1
            continue
        if line.startswith("|"):
            flush_paragraph()
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not all(set(c) <= {"-", ":", " "} for c in cells):
                table_rows.append(cells)
            i += 1
            continue
        if line.startswith("- "):
            flush_paragraph()
            flush_table()
            flow.append(
                Paragraph(
                    '<font name="Helvetica">•</font> ' + inline_markup(line[2:]),
                    styles["CnBullet"],
                )
            )
            i += 1
            continue
        if len(line) >= 2 and line[0].isdigit() and ". " in line[:4]:
            flush_paragraph()
            flush_table()
            flow.append(
                Paragraph(inline_markup(line), styles["CnBullet"])
            )
            i += 1
            continue
        if not line:
            flush_paragraph()
            flush_table()
            i += 1
            continue
        if line.endswith("  "):
            flush_paragraph()
            flush_table()
            if not title_done:
                flow.append(Paragraph(inline_markup(line.strip()), styles["CnSubtitle"]))
            else:
                subtitle_lines.append(line.strip())
            i += 1
            continue
        paragraph.append(line)
        i += 1

    flush_paragraph()
    flush_table()
    if subtitle_lines:
        # Metadata is already split into individual paragraphs when encountered.
        pass
    return flow


def build() -> None:
    markdown = SOURCE.read_text(encoding="utf-8")
    flow = parse_markdown(markdown)
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=19 * mm,
        bottomMargin=22 * mm,
        title="CS10005.02 Lab3 AttackLab 实验报告",
        author="Yutong Huang",
        subject="Computer Systems Lab3: AttackLab",
    )
    doc.build(flow, onFirstPage=page_decor, onLaterPages=page_decor)
    print(OUTPUT)


if __name__ == "__main__":
    build()
