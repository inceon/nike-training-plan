from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class WorkoutType(str, Enum):
    SPEED = "speed"
    ENDURANCE = "endurance"
    RECOVERY = "recovery"
    RACE_DAY = "race_day"


class WorkoutSubtype(str, Enum):
    TRACK = "track"
    HILLS = "hills"
    FARTLEK = "fartlek"
    TEMPO = "tempo"
    PROGRESSIVE_RUN = "progressive_run"
    STRENGTH = "strength"
    MARATHON = "marathon"
    EASY_RUN = "easy_run"
    RECOVERY_RUN = "recovery_run"
    UNKNOWN = "unknown"


class PaceType(str, Enum):
    KM_PACE = "km_pace"
    MILE_PACE = "mile_pace"
    PACE_5K = "pace_5k"
    PACE_10K = "pace_10k"
    THRESHOLD = "threshold"
    MARATHON_PACE = "marathon_pace"
    RECOVERY = "recovery"
    EASY = "easy"
    HARD = "hard"
    VERY_FAST = "very_fast"
    PROGRESSIVE = "progressive"
    UNKNOWN = "unknown"


class SourceTrace(BaseModel):
    page_numbers: list[int] = Field(default_factory=list)
    raw_text: str = ""


class DetectedSection(BaseModel):
    name: str
    page_start: int
    page_end: int
    page_numbers: list[int]


class DocumentMetadata(BaseModel):
    title: str
    language: str
    source_file: str
    total_pages: int
    detected_sections: list[DetectedSection]


class GuidanceAdvice(BaseModel):
    title: str
    text: str
    source: SourceTrace


class IntroSections(BaseModel):
    introduction_text: str
    weekly_training_explanation: str
    pace_guidance_text: str
    pace_examples_text: str
    weekly_overview_text: str
    if_you_advice: list[GuidanceAdvice] = Field(default_factory=list)


class GlossaryTerm(BaseModel):
    term: str
    category: str
    description: str
    source: SourceTrace


class PaceTableRow(BaseModel):
    row_index: int
    best_km_pace: str
    best_km_pace_seconds_per_km: int
    best_5k_result: str
    best_5k_result_seconds: int
    best_5k_pace: str
    best_5k_pace_seconds_per_km: int
    best_10k_result: str
    best_10k_result_seconds: int
    best_10k_pace: str
    best_10k_pace_seconds_per_km: int
    threshold_pace: str
    threshold_pace_seconds_per_km: int
    best_half_result: str
    best_half_result_seconds: int
    best_half_pace: str
    best_half_pace_seconds_per_km: int
    best_marathon_result: str
    best_marathon_result_seconds: int
    best_marathon_pace: str
    best_marathon_pace_seconds_per_km: int
    recovery_pace: str
    recovery_pace_seconds_per_km: int
    source: SourceTrace


class Segment(BaseModel):
    order: int
    distance_meters: Optional[int] = None
    distance_km: Optional[float] = None
    duration_seconds: Optional[int] = None
    repetitions: int = 1
    pace_type: PaceType = PaceType.UNKNOWN
    recovery_seconds: Optional[int] = None
    instructions: str = ""


class Workout(BaseModel):
    id: str
    workout_type: WorkoutType
    subtype: WorkoutSubtype
    title: str
    description: str
    segments: list[Segment] = Field(default_factory=list)
    recovery_between_segments: Optional[str] = None
    target_distance_km_min: Optional[float] = None
    target_distance_km_max: Optional[float] = None
    target_pace_type: PaceType = PaceType.UNKNOWN
    notes: list[str] = Field(default_factory=list)
    source: SourceTrace


class WeekPlan(BaseModel):
    week_number: int
    weeks_to_race: int
    headline: str
    summary: str
    workouts: list[Workout]
    recovery_guidance: list[str] = Field(default_factory=list)
    long_run: Optional[Workout] = None
    tags: list[str] = Field(default_factory=list)
    source_pages: list[int]
    raw_snippet: str


class ScheduleDayEntry(BaseModel):
    label: str
    workout_ref: Optional[str] = None
    workout_type: Optional[WorkoutType] = None
    subtype: Optional[WorkoutSubtype] = None


class SampleScheduleRow(BaseModel):
    week_number: int
    weeks_to_race: int
    monday: ScheduleDayEntry
    tuesday: ScheduleDayEntry
    wednesday: ScheduleDayEntry
    thursday: ScheduleDayEntry
    friday: ScheduleDayEntry
    saturday: ScheduleDayEntry
    sunday: ScheduleDayEntry
    source: SourceTrace


class TrainingPlanDocument(BaseModel):
    metadata: DocumentMetadata
    intro: IntroSections
    glossary: list[GlossaryTerm]
    pace_table: list[PaceTableRow]
    weeks: list[WeekPlan]
    sample_schedule: list[SampleScheduleRow]
