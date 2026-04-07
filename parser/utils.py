from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from parser.models import PaceType, WorkoutSubtype


WEEK_MARKER_RE = re.compile(r"ОСТАЛ(?:ОСЬ|АСЬ)\s+(\d+)", re.IGNORECASE)
TIME_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
REPEAT_RE = re.compile(
    r"^(?:\(\s*[xх×]\s*(\d+)\s*\)|(\d+)\s*[xх×]|повтори.*?(\d+)\s*раз)",
    re.IGNORECASE,
)
DISTANCE_RANGE_RE = re.compile(
    r"(?P<first>\d+(?:[.,]\d+)?)\s*(?:–|-)\s*(?P<second>\d+(?:[.,]\d+)?)\s*(?P<unit>км|километр(?:а|ов)?|метр(?:а|ов)?)",
    re.IGNORECASE,
)
HYPHENATED_DISTANCE_RANGE_RE = re.compile(
    r"(?P<first>\d+(?:[.,]\d+)?)\s*(?:–|-)\s*(?P<second>\d+(?:[.,]\d+)?)-(?P<unit>километров(?:ой|ых|ого)|метров(?:ой|ых|ого))",
    re.IGNORECASE,
)
DISTANCE_VALUE_RE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>км|километр(?:а|ов)?|метр(?:а|ов)?)",
    re.IGNORECASE,
)
HYPHENATED_DISTANCE_RE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)-(?P<unit>метров(?:ых|ого)?)",
    re.IGNORECASE,
)
RECOVERY_DURATION_RE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>секунд(?:ы)?|сек\.?|минут(?:ы)?|мин\.)\s+восстанов",
    re.IGNORECASE,
)


PACE_MAP: list[tuple[re.Pattern[str], PaceType]] = [
    (re.compile(r"километров(?:ом|ой)\s+темп", re.IGNORECASE), PaceType.KM_PACE),
    (re.compile(r"темпе\s+мили", re.IGNORECASE), PaceType.MILE_PACE),
    (re.compile(r"5-километров", re.IGNORECASE), PaceType.PACE_5K),
    (re.compile(r"10-километров", re.IGNORECASE), PaceType.PACE_10K),
    (re.compile(r"марафонск", re.IGNORECASE), PaceType.MARATHON_PACE),
    (re.compile(r"восстановител", re.IGNORECASE), PaceType.RECOVERY),
    (re.compile(r"спокойн", re.IGNORECASE), PaceType.EASY),
    (re.compile(r"удобн", re.IGNORECASE), PaceType.EASY),
    (re.compile(r"очень\s+быстр", re.IGNORECASE), PaceType.VERY_FAST),
    (re.compile(r"максимально\s+быстр", re.IGNORECASE), PaceType.VERY_FAST),
    (re.compile(r"коротк(?:их|ие)\s+забег", re.IGNORECASE), PaceType.VERY_FAST),
    (re.compile(r"бодр(?:ом|ый)\s+темп", re.IGNORECASE), PaceType.THRESHOLD),
    (re.compile(r"предельн", re.IGNORECASE), PaceType.THRESHOLD),
    (re.compile(r"прогрессив", re.IGNORECASE), PaceType.PROGRESSIVE),
]


@dataclass(frozen=True)
class DistanceRange:
    original: str
    min_value: float
    max_value: float
    unit: str

    @property
    def min_km(self) -> float:
        return meters_to_km(self.min_meters)

    @property
    def max_km(self) -> float:
        return meters_to_km(self.max_meters)

    @property
    def min_meters(self) -> int:
        return distance_to_meters(self.min_value, self.unit)

    @property
    def max_meters(self) -> int:
        return distance_to_meters(self.max_value, self.unit)


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = text.replace("\u2011", "-").replace("\u2013", "–").replace("\u2014", "—")
    text = text.replace("марафонскогобега", "марафонского бега")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", clean_text(text)).strip()


def split_nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in clean_text(text).splitlines() if line.strip()]


def normalize_ascii_slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return normalized or "item"


def parse_time_to_seconds(value: str) -> int:
    value = value.strip()
    if not TIME_RE.match(value):
        raise ValueError(f"Unsupported time format: {value!r}")
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


def parse_pace_string(value: str) -> int:
    return parse_time_to_seconds(value)


def parse_result_pace_pair(value: str) -> tuple[str, int, str, int]:
    result_text, pace_text = [part.strip() for part in value.split("/", 1)]
    return result_text, parse_time_to_seconds(result_text), pace_text, parse_pace_string(pace_text)


def extract_weeks_remaining(text: str) -> Optional[int]:
    match = WEEK_MARKER_RE.search(text)
    return int(match.group(1)) if match else None


def parse_repeat_count(text: str) -> Optional[int]:
    match = REPEAT_RE.search(text.strip())
    if not match:
        return None
    for group in match.groups():
        if group:
            return int(group)
    return None


def strip_repeat_prefix(text: str) -> str:
    return REPEAT_RE.sub("", text, count=1).strip(" .,:;-")


def parse_distance_range(text: str) -> Optional[DistanceRange]:
    match = DISTANCE_RANGE_RE.search(text)
    if match:
        unit = match.group("unit").lower()
        first = float(match.group("first").replace(",", "."))
        second = float(match.group("second").replace(",", "."))
        return DistanceRange(match.group(0), first, second, unit)

    match = HYPHENATED_DISTANCE_RANGE_RE.search(text)
    if match:
        unit = match.group("unit").lower()
        first = float(match.group("first").replace(",", "."))
        second = float(match.group("second").replace(",", "."))
        return DistanceRange(match.group(0), first, second, unit)

    match = HYPHENATED_DISTANCE_RE.search(text)
    if match:
        unit = match.group("unit").lower()
        value = float(match.group("value").replace(",", "."))
        return DistanceRange(match.group(0), value, value, unit)

    match = DISTANCE_VALUE_RE.search(text)
    if match:
        unit = match.group("unit").lower()
        value = float(match.group("value").replace(",", "."))
        return DistanceRange(match.group(0), value, value, unit)
    return None


def distance_to_meters(value: float, unit: str) -> int:
    if unit.startswith("км") or unit.startswith("километр"):
        return int(round(value * 1000))
    return int(round(value))


def meters_to_km(value: int) -> float:
    return round(value / 1000.0, 3)


def parse_recovery_duration(text: str) -> Optional[int]:
    match = RECOVERY_DURATION_RE.search(text)
    if not match:
        return None
    value = float(match.group("value").replace(",", "."))
    unit = match.group("unit").lower()
    if unit.startswith("мин"):
        return int(round(value * 60))
    return int(round(value))


def detect_pace_type(text: str) -> PaceType:
    for pattern, pace_type in PACE_MAP:
        if pattern.search(text):
            return pace_type
    return PaceType.UNKNOWN


def infer_subtype(title: str, description: str = "") -> WorkoutSubtype:
    text = f"{title} {description}"
    if re.search(r"трек", text, re.IGNORECASE):
        return WorkoutSubtype.TRACK
    if re.search(r"холмист", text, re.IGNORECASE):
        return WorkoutSubtype.HILLS
    if re.search(r"фартлек", text, re.IGNORECASE):
        return WorkoutSubtype.FARTLEK
    if re.search(r"прогрессив", text, re.IGNORECASE):
        return WorkoutSubtype.PROGRESSIVE_RUN
    if re.search(r"бодр(?:ый|ом)\s+темп", text, re.IGNORECASE):
        return WorkoutSubtype.TEMPO
    if re.search(r"сила", text, re.IGNORECASE):
        return WorkoutSubtype.STRENGTH
    if re.search(r"марафон", text, re.IGNORECASE):
        return WorkoutSubtype.MARATHON
    if re.search(r"восстанов", text, re.IGNORECASE):
        return WorkoutSubtype.RECOVERY_RUN
    if re.search(r"легк|простых километров|удобном темпе", text, re.IGNORECASE):
        return WorkoutSubtype.EASY_RUN
    return WorkoutSubtype.UNKNOWN


def is_upper_heading(text: str) -> bool:
    stripped = text.strip().replace("—", "").replace("-", "")
    if not stripped:
        return True
    letters = [char for char in stripped if char.isalpha()]
    if not letters:
        return False
    return all(char.isupper() for char in letters)


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def join_paragraphs(parts: Iterable[str]) -> str:
    cleaned = [collapse_whitespace(part) for part in parts if collapse_whitespace(part)]
    return "\n\n".join(cleaned)
