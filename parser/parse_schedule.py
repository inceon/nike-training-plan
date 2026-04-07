from __future__ import annotations

from collections import defaultdict

import fitz

from parser.models import PaceType, SampleScheduleRow, ScheduleDayEntry, SourceTrace, WeekPlan, Workout, WorkoutSubtype, WorkoutType
from parser.utils import collapse_whitespace, infer_subtype, parse_distance_range


DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
COLUMN_BOUNDS = {
    "week": (20, 55),
    "monday": (55, 135),
    "tuesday": (135, 205),
    "wednesday": (205, 285),
    "thursday": (285, 365),
    "friday": (365, 445),
    "saturday": (445, 510),
    "sunday": (510, 590),
}


def parse_sample_schedule(page: fitz.Page, weeks: list[WeekPlan]) -> list[SampleScheduleRow]:
    words = page.get_text("words")
    body_words = [word for word in words if 190 < word[1] < 760]
    rows = [row for row in _cluster_rows(body_words) if _looks_like_schedule_row(row)]
    if len(rows) != 18:
        raise ValueError(f"Expected 18 schedule rows, found {len(rows)}")

    week_lookup = {week.weeks_to_race: week for week in weeks}
    parsed_rows: list[SampleScheduleRow] = []

    for row_words in rows:
        cells = _row_cells(row_words)
        weeks_to_race = int(cells["week"])
        week = week_lookup.get(weeks_to_race)
        if week is None:
            raise ValueError(f"Missing week model for weeks_to_race={weeks_to_race}")

        row_kwargs = {
            "week_number": week.week_number,
            "weeks_to_race": weeks_to_race,
            "source": SourceTrace(page_numbers=[page.number + 1], raw_text=" | ".join(cells[name] for name in ["week", *DAY_NAMES])),
        }
        for day in DAY_NAMES:
            row_kwargs[day] = _build_day_entry(day, cells[day], week)

        parsed_rows.append(SampleScheduleRow(**row_kwargs))

    parsed_rows.sort(key=lambda row: row.week_number)
    return parsed_rows


def _cluster_rows(words: list[tuple]) -> list[list[tuple]]:
    sorted_words = sorted(words, key=lambda item: (item[1], item[0]))
    clusters: list[list[tuple]] = []
    for word in sorted_words:
        if not clusters:
            clusters.append([word])
            continue
        current = clusters[-1]
        avg_y = sum(item[1] for item in current) / len(current)
        if abs(word[1] - avg_y) <= 18:
            current.append(word)
        else:
            clusters.append([word])
    return clusters


def _looks_like_schedule_row(row_words: list[tuple]) -> bool:
    first = min(row_words, key=lambda item: item[0])[4]
    return first.isdigit()


def _row_cells(row_words: list[tuple]) -> dict[str, str]:
    grouped: dict[str, list[tuple]] = defaultdict(list)
    for word in sorted(row_words, key=lambda item: (item[0], item[1])):
        text = word[4]
        x_mid = (word[0] + word[2]) / 2
        for column, (start, end) in COLUMN_BOUNDS.items():
            if start <= x_mid < end:
                grouped[column].append(word)
                break

    cells: dict[str, str] = {}
    for column in COLUMN_BOUNDS:
        ordered = sorted(grouped.get(column, []), key=lambda item: (item[1], item[0]))
        cells[column] = collapse_whitespace(" ".join(item[4] for item in ordered))
    if not cells["week"]:
        raise ValueError(f"Unable to parse schedule row: {row_words!r}")
    return cells


def _build_day_entry(day_name: str, label: str, week: WeekPlan) -> ScheduleDayEntry:
    workout = _match_workout(day_name, label, week)
    if workout is None:
        return ScheduleDayEntry(label=label)
    return ScheduleDayEntry(
        label=label,
        workout_ref=workout.id,
        workout_type=workout.workout_type,
        subtype=workout.subtype,
    )


def _match_workout(day_name: str, label: str, week: WeekPlan) -> Workout | None:
    label_upper = label.upper()
    speed_workouts = [workout for workout in week.workouts if workout.workout_type == WorkoutType.SPEED]
    recovery_workouts = [workout for workout in week.workouts if workout.workout_type == WorkoutType.RECOVERY]

    if day_name == "tuesday":
        return speed_workouts[0] if speed_workouts else None
    if day_name == "thursday":
        return speed_workouts[1] if len(speed_workouts) > 1 else None
    if day_name == "saturday":
        return _match_long_run_like(label, week)
    if day_name == "sunday" and "МАРАФОН" in label_upper:
        return week.long_run
    if day_name == "monday":
        return _match_recovery_by_distance(label, recovery_workouts)
    if day_name == "friday":
        return _match_recovery_by_distance(label, recovery_workouts)
    if day_name in {"wednesday", "sunday"} and "ВОССТАНОВЛЕНИЕ" in label_upper:
        generic = [workout for workout in recovery_workouts if workout.target_distance_km_min is None]
        if not generic:
            return None
        return generic[0] if day_name == "wednesday" else generic[1] if len(generic) > 1 else generic[0]
    if "ТРЕК" in label_upper:
        for workout in speed_workouts:
            if workout.subtype == WorkoutSubtype.TRACK:
                return workout
    subtype = infer_subtype(label)
    for workout in speed_workouts:
        if workout.subtype == subtype:
            return workout
    return None


def _match_recovery_by_distance(label: str, workouts: list[Workout]) -> Workout | None:
    wanted = parse_distance_range(label)
    if wanted is None:
        return None
    for workout in workouts:
        if workout.target_distance_km_min == wanted.min_km and workout.target_distance_km_max == wanted.max_km:
            return workout
    return None


def _match_long_run_like(label: str, week: WeekPlan) -> Workout | None:
    if week.long_run is None:
        return None
    if "МАРАФОН" in label.upper():
        return week.long_run
    wanted = parse_distance_range(label)
    if wanted is None:
        return None
    if (
        week.long_run.target_distance_km_min == wanted.min_km
        and week.long_run.target_distance_km_max == wanted.max_km
    ):
        return week.long_run
    return None
