from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import fitz

from parser.extract import TextBlock, extract_blocks
from parser.models import PaceType, Segment, SourceTrace, WeekPlan, Workout, WorkoutSubtype, WorkoutType
from parser.utils import (
    DistanceRange,
    collapse_whitespace,
    detect_pace_type,
    extract_weeks_remaining,
    infer_subtype,
    is_upper_heading,
    join_paragraphs,
    normalize_ascii_slug,
    parse_distance_range,
    parse_recovery_duration,
    parse_repeat_count,
    split_nonempty_lines,
    strip_repeat_prefix,
)


HEADER_RECT = fitz.Rect(60, 20, 550, 170)
CENTER_RECT = fitz.Rect(210, 180, 400, 740)
LEFT_RECT = fitz.Rect(25, 280, 200, 650)
RIGHT_RECT = fitz.Rect(410, 280, 585, 650)
MAIN_HEADINGS = {"СКОРОСТЬ", "ВЫНОСЛИВОСТЬ", "ДЕНЬ ЗАБЕГА"}
RECOVERY_HEADING = "ВОССТАНОВЛЕНИЕ"


@dataclass
class RawSection:
    heading: str
    blocks: list[TextBlock] = field(default_factory=list)


def parse_week_pages(doc: fitz.Document, page_numbers: list[int]) -> list[WeekPlan]:
    weeks: list[WeekPlan] = []
    for sequential_week, page_number in enumerate(sorted(page_numbers), start=1):
        weeks.append(parse_week_page(doc[page_number - 1], sequential_week))
    return weeks


def parse_week_page(page: fitz.Page, week_number: int) -> WeekPlan:
    header_blocks = extract_blocks(page, clip=HEADER_RECT)
    center_blocks = extract_blocks(page, clip=CENTER_RECT)
    left_blocks = extract_blocks(page, clip=LEFT_RECT)
    right_blocks = extract_blocks(page, clip=RIGHT_RECT)

    header_text = "\n".join(block.text for block in header_blocks)
    weeks_to_race = extract_weeks_remaining(header_text)
    if weeks_to_race is None:
        raise ValueError(f"Unable to detect weeks remaining on page {page.number + 1}")

    headline, summary = _parse_header(header_blocks)
    center_sections = _split_sections(center_blocks, MAIN_HEADINGS)
    if len(center_sections) != 3:
        raise ValueError(f"Expected 3 center sections on page {page.number + 1}, found {len(center_sections)}")

    workouts: list[Workout] = []
    id_counters: dict[str, int] = defaultdict(int)
    for section in center_sections:
        workouts.append(_parse_center_workout(section, week_number, page.number + 1, id_counters))

    recovery_sections = _split_recovery_sections(left_blocks) + _split_recovery_sections(right_blocks)
    recovery_sections.sort(key=lambda section: (section.blocks[0].y0, section.blocks[0].x0))
    for section in recovery_sections:
        workouts.append(_parse_recovery_workout(section, week_number, page.number + 1, id_counters))

    long_run = next(
        (workout for workout in workouts if workout.workout_type in {WorkoutType.ENDURANCE, WorkoutType.RACE_DAY}),
        None,
    )
    if long_run is None:
        raise ValueError(f"Week page {page.number + 1} is missing a long run or race-day block.")

    recovery_guidance = [
        workout.description
        for workout in workouts
        if workout.workout_type == WorkoutType.RECOVERY and workout.description
    ]
    tags = sorted(
        {
            workout.subtype.value
            for workout in workouts
            if workout.subtype != WorkoutSubtype.UNKNOWN
        }
        | {"long_run"}
    )

    return WeekPlan(
        week_number=week_number,
        weeks_to_race=weeks_to_race,
        headline=headline,
        summary=summary,
        workouts=workouts,
        recovery_guidance=recovery_guidance,
        long_run=long_run,
        tags=tags,
        source_pages=[page.number + 1],
        raw_snippet=collapse_whitespace(f"{headline} {summary}"),
    )


def _parse_header(header_blocks: list[TextBlock]) -> tuple[str, str]:
    filtered = [block for block in header_blocks if "ОСТАЛ" not in block.text.upper()]
    if len(filtered) < 2:
        raise ValueError("Week header does not contain a headline and summary.")
    headline = collapse_whitespace(filtered[0].text)
    summary = join_paragraphs(block.text for block in filtered[1:])
    return headline, summary


def _split_sections(blocks: list[TextBlock], heading_names: set[str]) -> list[RawSection]:
    sections: list[RawSection] = []
    current: RawSection | None = None
    for block in blocks:
        heading = collapse_whitespace(block.text).upper()
        if heading in heading_names:
            if current is not None:
                sections.append(current)
            current = RawSection(heading=heading, blocks=[block])
        elif current is not None:
            current.blocks.append(block)
    if current is not None:
        sections.append(current)
    return sections


def _split_recovery_sections(blocks: list[TextBlock]) -> list[RawSection]:
    sections: list[RawSection] = []
    current: RawSection | None = None
    for block in blocks:
        text = collapse_whitespace(block.text).upper()
        if text == RECOVERY_HEADING:
            if current is not None:
                sections.append(current)
            current = RawSection(heading=RECOVERY_HEADING, blocks=[block])
        elif current is not None:
            current.blocks.append(block)
    if current is not None:
        sections.append(current)
    return sections


def _parse_center_workout(
    section: RawSection,
    week_number: int,
    page_number: int,
    id_counters: dict[str, int],
) -> Workout:
    workout_type = _heading_to_workout_type(section.heading)
    title_blocks, content_blocks = _split_title_blocks(section.blocks[1:])
    title = _normalize_title(title_blocks)
    description = join_paragraphs(block.text for block in content_blocks)
    subtype = infer_subtype(title, description)
    if workout_type == WorkoutType.ENDURANCE and subtype == WorkoutSubtype.UNKNOWN:
        subtype = WorkoutSubtype.EASY_RUN
    if workout_type == WorkoutType.RACE_DAY:
        subtype = WorkoutSubtype.MARATHON

    segments, recovery_text, notes = _parse_segments(content_blocks)
    target_distance = parse_distance_range(title) or parse_distance_range(description)
    target_pace_type = _derive_target_pace_type(description, segments, subtype)

    return Workout(
        id=_build_workout_id(week_number, workout_type, subtype, id_counters),
        workout_type=workout_type,
        subtype=subtype,
        title=title,
        description=description,
        segments=segments,
        recovery_between_segments=recovery_text,
        target_distance_km_min=target_distance.min_km if target_distance else None,
        target_distance_km_max=target_distance.max_km if target_distance else None,
        target_pace_type=target_pace_type,
        notes=notes,
        source=SourceTrace(page_numbers=[page_number], raw_text=collapse_whitespace(f"{section.heading} {title} {description}")),
    )


def _parse_recovery_workout(
    section: RawSection,
    week_number: int,
    page_number: int,
    id_counters: dict[str, int],
) -> Workout:
    description_blocks = [block for block in section.blocks[1:] if collapse_whitespace(block.text) != "—"]
    description = join_paragraphs(block.text for block in description_blocks)
    distance = parse_distance_range(description)
    subtype = infer_subtype("ВОССТАНОВЛЕНИЕ", description)
    if subtype == WorkoutSubtype.UNKNOWN:
        subtype = WorkoutSubtype.RECOVERY_RUN
    target_pace_type = PaceType.PROGRESSIVE if "прогрессив" in description.lower() else PaceType.RECOVERY
    segments: list[Segment] = []
    if distance is not None:
        segments.append(
            Segment(
                order=1,
                distance_meters=distance.max_meters if distance.min_meters == distance.max_meters else None,
                distance_km=distance.max_km if distance.min_km == distance.max_km else None,
                pace_type=target_pace_type,
                instructions=description,
            )
        )

    return Workout(
        id=_build_workout_id(week_number, WorkoutType.RECOVERY, subtype, id_counters),
        workout_type=WorkoutType.RECOVERY,
        subtype=subtype,
        title=RECOVERY_HEADING,
        description=description,
        segments=segments,
        recovery_between_segments=None,
        target_distance_km_min=distance.min_km if distance else None,
        target_distance_km_max=distance.max_km if distance else None,
        target_pace_type=target_pace_type,
        notes=[],
        source=SourceTrace(page_numbers=[page_number], raw_text=collapse_whitespace(description)),
    )


def _heading_to_workout_type(heading: str) -> WorkoutType:
    if heading == "СКОРОСТЬ":
        return WorkoutType.SPEED
    if heading == "ВЫНОСЛИВОСТЬ":
        return WorkoutType.ENDURANCE
    return WorkoutType.RACE_DAY


def _split_title_blocks(blocks: list[TextBlock]) -> tuple[list[TextBlock], list[TextBlock]]:
    title_blocks: list[TextBlock] = []
    content_blocks: list[TextBlock] = []
    title_complete = False
    for block in blocks:
        text = collapse_whitespace(block.text)
        if not title_complete and (is_upper_heading(text) or text.startswith("—")):
            title_blocks.append(block)
            continue
        title_complete = True
        content_blocks.append(block)
    return title_blocks, content_blocks


def _normalize_title(blocks: list[TextBlock]) -> str:
    title = collapse_whitespace(" ".join(block.text for block in blocks))
    title = title.replace("— ", "").replace(" —", "").strip("— ").strip()
    return title


def _build_workout_id(
    week_number: int,
    workout_type: WorkoutType,
    subtype: WorkoutSubtype,
    counters: dict[str, int],
) -> str:
    key = f"{workout_type.value}:{subtype.value}"
    counters[key] += 1
    suffix = counters[key]
    return f"week-{week_number:02d}-{normalize_ascii_slug(workout_type.value)}-{normalize_ascii_slug(subtype.value)}-{suffix}"


def _parse_segments(blocks: list[TextBlock]) -> tuple[list[Segment], str | None, list[str]]:
    lines: list[str] = []
    for block in blocks:
        lines.extend(split_nonempty_lines(block.text))

    segments: list[Segment] = []
    recovery_lines: list[str] = []
    notes: list[str] = []

    for line in lines:
        normalized = collapse_whitespace(line)
        if _is_recovery_instruction(normalized):
            recovery_lines.append(normalized)
            continue
        if normalized.lower().startswith("повтори"):
            notes.append(normalized)
            continue
        if normalized.lower().startswith("затем выполни"):
            notes.append(normalized)
            continue
        created = _segments_from_line(normalized, len(segments) + 1)
        if created:
            segments.extend(created)
        else:
            notes.append(normalized)

    recovery_text = join_paragraphs(recovery_lines) if recovery_lines else None
    return segments, recovery_text or None, notes


def _is_recovery_instruction(line: str) -> bool:
    lower = line.lower()
    if lower.startswith("восстановление") or lower.startswith("после каждого"):
        return True
    if "после каждого" in lower:
        return True
    if "восстановления после" in lower or "отдыха после" in lower:
        return True
    if parse_recovery_duration(line) is not None and "после" in lower:
        return True
    if lower.startswith("2 минуты восстановления") or lower.startswith("60 секунд восстановления"):
        return True
    return False


def _segments_from_line(line: str, order_start: int) -> list[Segment]:
    if "," in line and "восстанов" not in line.lower() and _count_segmentable_parts(line) > 1:
        pieces = [piece.strip() for piece in line.split(",") if piece.strip()]
        segments: list[Segment] = []
        order = order_start
        for piece in pieces:
            parsed = _segment_from_fragment(piece, order)
            if parsed is not None:
                segments.append(parsed)
                order += 1
        return segments

    parsed = _segment_from_fragment(line, order_start)
    return [parsed] if parsed is not None else []


def _count_segmentable_parts(line: str) -> int:
    return sum(1 for piece in line.split(",") if parse_distance_range(piece) or _parse_duration_only(piece))


def _segment_from_fragment(fragment: str, order: int) -> Segment | None:
    repetitions = parse_repeat_count(fragment) or 1
    text = strip_repeat_prefix(fragment)
    inline_recovery = parse_recovery_duration(text)
    pace_type = detect_pace_type(text)
    distance = parse_distance_range(text)
    duration_seconds = _parse_duration_only(text)

    if distance is None and duration_seconds is None:
        return None

    return Segment(
        order=order,
        distance_meters=_distance_for_segment(distance),
        distance_km=_distance_km_for_segment(distance),
        duration_seconds=duration_seconds,
        repetitions=repetitions,
        pace_type=pace_type,
        recovery_seconds=inline_recovery,
        instructions=text,
    )


def _distance_for_segment(distance: DistanceRange | None) -> int | None:
    if distance is None or distance.min_meters != distance.max_meters:
        return None
    return distance.max_meters


def _distance_km_for_segment(distance: DistanceRange | None) -> float | None:
    if distance is None or distance.min_km != distance.max_km:
        return None
    return distance.max_km


def _parse_duration_only(text: str) -> int | None:
    lower = text.lower()
    if "восстанов" in lower and parse_distance_range(text) is None:
        return None
    for token in split_nonempty_lines(text.replace(",", "\n")):
        words = token.split()
        if len(words) < 2:
            continue
        value = words[0].replace(",", ".")
        unit = words[1].lower()
        if not value.replace(".", "", 1).isdigit():
            continue
        number = float(value)
        if unit.startswith("мин"):
            return int(round(number * 60))
        if unit.startswith("сек"):
            return int(round(number))
    return None


def _derive_target_pace_type(description: str, segments: list[Segment], subtype: WorkoutSubtype) -> PaceType:
    if subtype == WorkoutSubtype.PROGRESSIVE_RUN:
        return PaceType.PROGRESSIVE
    if subtype == WorkoutSubtype.TEMPO:
        return PaceType.THRESHOLD
    if subtype == WorkoutSubtype.RECOVERY_RUN:
        return PaceType.RECOVERY
    explicit = detect_pace_type(description)
    if explicit != PaceType.UNKNOWN:
        return explicit
    for segment in segments:
        if segment.pace_type != PaceType.UNKNOWN:
            return segment.pace_type
    if subtype == WorkoutSubtype.EASY_RUN:
        return PaceType.EASY
    return PaceType.UNKNOWN
