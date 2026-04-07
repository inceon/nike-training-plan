from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import fitz

from parser.utils import clean_text, collapse_whitespace


@dataclass(frozen=True)
class TextBlock:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


@dataclass(frozen=True)
class PageSnapshot:
    page_number: int
    text: str
    blocks: list[TextBlock]
    page_type: str


def load_pdf(path: str | Path) -> fitz.Document:
    return fitz.open(str(path))


def extract_blocks(page: fitz.Page, clip: fitz.Rect | None = None) -> list[TextBlock]:
    raw_blocks = page.get_text("blocks", clip=clip)
    blocks = [
        TextBlock(
            x0=block[0],
            y0=block[1],
            x1=block[2],
            y1=block[3],
            text=clean_text(block[4]),
        )
        for block in raw_blocks
        if clean_text(block[4])
    ]
    return sorted(blocks, key=lambda item: (round(item.y0, 1), item.x0))


def extract_page_text(page: fitz.Page, clip: fitz.Rect | None = None) -> str:
    return clean_text(page.get_text("text", clip=clip))


def snapshot_document(doc: fitz.Document) -> list[PageSnapshot]:
    snapshots: list[PageSnapshot] = []
    for index in range(doc.page_count):
        page = doc[index]
        text = extract_page_text(page)
        blocks = extract_blocks(page)
        snapshots.append(
            PageSnapshot(
                page_number=index + 1,
                text=text,
                blocks=blocks,
                page_type=classify_page(index + 1, text),
            )
        )
    return snapshots


def classify_page(page_number: int, text: str) -> str:
    upper = collapse_whitespace(text).upper()
    if "МАРАФОН" in upper and "18-НЕДЕЛЬНАЯ ПРОГРАММА" in upper and page_number == 1:
        return "cover"
    if "СОДЕРЖАНИЕ" in upper:
        return "contents"
    if page_number == 4:
        return "introduction"
    if page_number == 5:
        return "weekly_concepts"
    if page_number == 6:
        return "pace_guidance"
    if page_number == 7:
        return "pace_examples"
    if "ТАБЛИЦА ТЕМПОВ" in upper and page_number == 8:
        return "pace_table"
    if "ГЛОССАРИЙ" in upper:
        return "glossary"
    if "ПРИМЕР РАСПИСАНИЯ" in upper:
        return "sample_schedule"
    if "ПОНЕДЕЛЬНЫЙ ОБЗОР МАРАФОНА" in upper:
        return "weekly_overview"
    if "ЕСЛИ ТЫ" in upper and page_number == 10:
        return "guidance"
    if ("ОСТАЛОСЬ" in upper or "ОСТАЛАСЬ" in upper) and (
        "СКОРОСТЬ" in upper or "ДЕНЬ ЗАБЕГА" in upper
    ):
        return "week"
    if page_number == 31 or "БЕГАЙ ПО-НОВОМУ" in upper:
        return "closing_promo"
    if page_number == 2:
        return "hero"
    return "reference"


def collect_pages(snapshots: Iterable[PageSnapshot], page_type: str) -> list[PageSnapshot]:
    return [snapshot for snapshot in snapshots if snapshot.page_type == page_type]
