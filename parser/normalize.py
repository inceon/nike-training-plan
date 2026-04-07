from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import fitz

from parser.extract import PageSnapshot, TextBlock, collect_pages, load_pdf, snapshot_document
from parser.models import (
    DetectedSection,
    DocumentMetadata,
    GlossaryTerm,
    GuidanceAdvice,
    IntroSections,
    SourceTrace,
    TrainingPlanDocument,
    WeekPlan,
)
from parser.parse_pace_table import parse_pace_table
from parser.parse_schedule import parse_sample_schedule
from parser.parse_weeks import parse_week_pages
from parser.utils import clean_text, collapse_whitespace, join_paragraphs


def parse_training_pdf(pdf_path: str | Path) -> TrainingPlanDocument:
    pdf_path = Path(pdf_path)
    doc = load_pdf(pdf_path)
    snapshots = snapshot_document(doc)

    intro = _parse_intro_sections(doc, snapshots)
    glossary = _parse_glossary(doc, snapshots)
    pace_table = parse_pace_table(pdf_path, doc, page_number=8)
    weeks = parse_week_pages(doc, [snapshot.page_number for snapshot in collect_pages(snapshots, "week")])
    schedule_page = collect_pages(snapshots, "sample_schedule")
    if len(schedule_page) != 1:
        raise ValueError(f"Expected exactly one sample schedule page, found {len(schedule_page)}")
    sample_schedule = parse_sample_schedule(doc[schedule_page[0].page_number - 1], weeks)

    metadata = DocumentMetadata(
        title="Nike Run Club Marathon 18-Week Training Plan",
        language="ru",
        source_file=str(pdf_path),
        total_pages=doc.page_count,
        detected_sections=_build_detected_sections(snapshots),
    )
    document = TrainingPlanDocument(
        metadata=metadata,
        intro=intro,
        glossary=glossary,
        pace_table=pace_table,
        weeks=weeks,
        sample_schedule=sample_schedule,
    )
    _validate_document(document)
    return document


def _parse_intro_sections(doc: fitz.Document, snapshots: list[PageSnapshot]) -> IntroSections:
    page_map = {snapshot.page_type: snapshot for snapshot in snapshots}
    guidance_page = page_map["guidance"]
    return IntroSections(
        introduction_text=_page_text(doc, page_map["introduction"].page_number),
        weekly_training_explanation=_page_text(doc, page_map["weekly_concepts"].page_number),
        pace_guidance_text=_page_text(doc, page_map["pace_guidance"].page_number),
        pace_examples_text=_page_text(doc, page_map["pace_examples"].page_number),
        weekly_overview_text=_page_text(doc, page_map["weekly_overview"].page_number),
        if_you_advice=_parse_guidance_page(doc[guidance_page.page_number - 1], guidance_page.page_number),
    )


def _page_text(doc: fitz.Document, page_number: int) -> str:
    return clean_text(doc[page_number - 1].get_text("text"))


def _parse_guidance_page(page: fitz.Page, page_number: int) -> list[GuidanceAdvice]:
    blocks = sorted(page.get_text("blocks"), key=lambda item: (round(item[1], 1), item[0]))
    sections: list[GuidanceAdvice] = []
    current_title: str | None = None
    current_parts: list[str] = []

    for block in blocks:
        text = clean_text(block[4])
        collapsed = collapse_whitespace(text)
        if not collapsed:
            continue
        if collapsed.startswith("ЕСЛИ "):
            if current_title is not None:
                sections.append(
                    GuidanceAdvice(
                        title=current_title,
                        text=join_paragraphs(current_parts),
                        source=SourceTrace(page_numbers=[page_number], raw_text=collapse_whitespace(f"{current_title} {' '.join(current_parts)}")),
                    )
                )
            current_title = collapsed
            current_parts = []
        elif current_title is not None and not collapsed.startswith("У КАЖДОГО") and not collapsed.startswith("НО НЕКОТОРЫЕ"):
            current_parts.append(text)

    if current_title is not None:
        sections.append(
            GuidanceAdvice(
                title=current_title,
                text=join_paragraphs(current_parts),
                source=SourceTrace(page_numbers=[page_number], raw_text=collapse_whitespace(f"{current_title} {' '.join(current_parts)}")),
            )
        )
    return sections


def _parse_glossary(doc: fitz.Document, snapshots: list[PageSnapshot]) -> list[GlossaryTerm]:
    glossary_snapshot = collect_pages(snapshots, "glossary")
    if len(glossary_snapshot) != 1:
        raise ValueError(f"Expected one glossary page, found {len(glossary_snapshot)}")
    page_number = glossary_snapshot[0].page_number
    page = doc[page_number - 1]

    terms: list[GlossaryTerm] = []
    regions = [
        ("тренировки", [fitz.Rect(20, 150, 210, 260), fitz.Rect(210, 150, 400, 260), fitz.Rect(400, 150, 592, 260)]),
        ("типы пробежек", [fitz.Rect(20, 330, 210, 610), fitz.Rect(210, 330, 400, 610), fitz.Rect(400, 330, 592, 610)]),
        (
            "типы темпа",
            [
                fitz.Rect(20, 670, 135, 730),
                fitz.Rect(135, 670, 250, 730),
                fitz.Rect(250, 670, 365, 730),
                fitz.Rect(365, 670, 490, 730),
                fitz.Rect(490, 670, 592, 730),
            ],
        ),
    ]

    for category, rects in regions:
        for rect in rects:
            terms.extend(_parse_glossary_region(page, page_number, rect, category))
    return terms


def _looks_like_glossary_term(text: str) -> bool:
    if len(text) < 4:
        return False
    if any(ch.islower() for ch in text):
        return False
    return True


def _make_glossary_term(term: str, category: str, parts: list[str], page_number: int) -> GlossaryTerm:
    description = join_paragraphs(parts)
    return GlossaryTerm(
        term=term,
        category=category,
        description=description,
        source=SourceTrace(page_numbers=[page_number], raw_text=collapse_whitespace(f"{term} {' '.join(parts)}")),
    )


def _parse_glossary_region(page: fitz.Page, page_number: int, rect: fitz.Rect, category: str) -> list[GlossaryTerm]:
    blocks = _blocks_in_rect(page, rect)
    terms: list[GlossaryTerm] = []
    current_term: str | None = None
    current_parts: list[str] = []

    for block in blocks:
        text = collapse_whitespace(block.text)
        if not text:
            continue
        if text in {"ТИПЫ ПРОБЕЖЕК", "ТИПЫ ТЕМПА", "ТРЕНИРОВКИ"}:
            continue
        if _looks_like_glossary_term(text):
            if current_term is not None and not current_parts:
                current_term = collapse_whitespace(f"{current_term} {text}")
                continue
            if current_term is not None and current_parts:
                terms.append(_make_glossary_term(current_term, category, current_parts, page_number))
            current_term = text
            current_parts = []
            continue
        if current_term is not None:
            current_parts.append(block.text)

    if current_term is not None and current_parts:
        terms.append(_make_glossary_term(current_term, category, current_parts, page_number))
    return terms


def _blocks_in_rect(page: fitz.Page, rect: fitz.Rect) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    for raw in page.get_text("blocks"):
        x0, y0, x1, y1, text, *_ = raw
        cleaned = clean_text(text)
        if not cleaned:
            continue
        x_mid = (x0 + x1) / 2
        y_mid = (y0 + y1) / 2
        if rect.x0 <= x_mid <= rect.x1 and rect.y0 <= y_mid <= rect.y1:
            blocks.append(TextBlock(x0=x0, y0=y0, x1=x1, y1=y1, text=cleaned))
    return sorted(blocks, key=lambda block: (round(block.y0, 1), block.x0))


def _build_detected_sections(snapshots: list[PageSnapshot]) -> list[DetectedSection]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for snapshot in snapshots:
        grouped[snapshot.page_type].append(snapshot.page_number)

    sections: list[DetectedSection] = []
    for name, pages in grouped.items():
        sections.append(
            DetectedSection(
                name=name,
                page_start=min(pages),
                page_end=max(pages),
                page_numbers=sorted(pages),
            )
        )
    return sorted(sections, key=lambda section: section.page_start)


def _validate_document(document: TrainingPlanDocument) -> None:
    if len(document.weeks) != 18:
        raise ValueError(f"Expected 18 weeks, found {len(document.weeks)}")
    if len(document.sample_schedule) != 18:
        raise ValueError(f"Expected 18 sample schedule rows, found {len(document.sample_schedule)}")
    if not document.pace_table:
        raise ValueError("Pace table is empty.")

    for week in document.weeks:
        if week.long_run is None:
            raise ValueError(f"Week {week.week_number} is missing long_run")
        recovery_count = sum(1 for workout in week.workouts if workout.workout_type.value == "recovery")
        if recovery_count == 0:
            raise ValueError(f"Week {week.week_number} has no recovery workouts.")
