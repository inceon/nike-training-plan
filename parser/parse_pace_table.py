from __future__ import annotations

from pathlib import Path

import fitz
import pdfplumber

from parser.models import PaceTableRow, SourceTrace
from parser.utils import collapse_whitespace, parse_pace_string, parse_result_pace_pair


EXPECTED_COLUMNS = 7


def parse_pace_table(pdf_path: str | Path, doc: fitz.Document, page_number: int = 8) -> list[PaceTableRow]:
    rows = _extract_table_with_pdfplumber(pdf_path, page_number)
    if not rows:
        rows = _extract_table_with_fitz(doc, page_number)
    if not rows:
        raise ValueError("Unable to extract pace table rows.")
    return [_build_row(index, row, page_number) for index, row in enumerate(rows, start=1)]


def _extract_table_with_pdfplumber(pdf_path: str | Path, page_number: int) -> list[list[str]]:
    with pdfplumber.open(str(pdf_path)) as pdf:
        page = pdf.pages[page_number - 1]
        tables = page.extract_tables()
        if not tables:
            return []
        table = tables[0]
    return [
        [collapse_whitespace(cell or "") for cell in row]
        for row in table[1:]
        if row and len(row) == EXPECTED_COLUMNS and collapse_whitespace(" ".join(cell or "" for cell in row))
    ]


def _extract_table_with_fitz(doc: fitz.Document, page_number: int) -> list[list[str]]:
    page = doc[page_number - 1]
    rows: list[list[str]] = []
    for block in page.get_text("blocks"):
        x0, y0, _, _, text, *_ = block
        line = collapse_whitespace(text)
        if x0 < 100 and y0 > 160 and "/" in line:
            rows.append(_split_fitz_row(line))
    return rows


def _split_fitz_row(row_text: str) -> list[str]:
    pieces = row_text.split()
    if len(pieces) < 11:
        raise ValueError(f"Unexpected pace table row: {row_text!r}")
    return [
        pieces[0],
        f"{pieces[1]} {pieces[2]} {pieces[3]}",
        f"{pieces[4]} {pieces[5]} {pieces[6]}",
        pieces[7],
        f"{pieces[8]} {pieces[9]} {pieces[10]}",
        f"{pieces[11]} {pieces[12]} {pieces[13]}",
        pieces[14],
    ]


def _build_row(row_index: int, values: list[str], page_number: int) -> PaceTableRow:
    if len(values) != EXPECTED_COLUMNS:
        raise ValueError(f"Unexpected pace table column count: {len(values)}")

    best_5k_result, best_5k_result_seconds, best_5k_pace, best_5k_pace_seconds = parse_result_pace_pair(values[1])
    best_10k_result, best_10k_result_seconds, best_10k_pace, best_10k_pace_seconds = parse_result_pace_pair(values[2])
    best_half_result, best_half_result_seconds, best_half_pace, best_half_pace_seconds = parse_result_pace_pair(values[4])
    best_marathon_result, best_marathon_result_seconds, best_marathon_pace, best_marathon_pace_seconds = parse_result_pace_pair(
        values[5]
    )

    return PaceTableRow(
        row_index=row_index,
        best_km_pace=values[0],
        best_km_pace_seconds_per_km=parse_pace_string(values[0]),
        best_5k_result=best_5k_result,
        best_5k_result_seconds=best_5k_result_seconds,
        best_5k_pace=best_5k_pace,
        best_5k_pace_seconds_per_km=best_5k_pace_seconds,
        best_10k_result=best_10k_result,
        best_10k_result_seconds=best_10k_result_seconds,
        best_10k_pace=best_10k_pace,
        best_10k_pace_seconds_per_km=best_10k_pace_seconds,
        threshold_pace=values[3],
        threshold_pace_seconds_per_km=parse_pace_string(values[3]),
        best_half_result=best_half_result,
        best_half_result_seconds=best_half_result_seconds,
        best_half_pace=best_half_pace,
        best_half_pace_seconds_per_km=best_half_pace_seconds,
        best_marathon_result=best_marathon_result,
        best_marathon_result_seconds=best_marathon_result_seconds,
        best_marathon_pace=best_marathon_pace,
        best_marathon_pace_seconds_per_km=best_marathon_pace_seconds,
        recovery_pace=values[6],
        recovery_pace_seconds_per_km=parse_pace_string(values[6]),
        source=SourceTrace(page_numbers=[page_number], raw_text=" | ".join(values)),
    )
