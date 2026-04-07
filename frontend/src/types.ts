export type PaceType =
  | "km_pace"
  | "mile_pace"
  | "pace_5k"
  | "pace_10k"
  | "threshold"
  | "marathon_pace"
  | "recovery"
  | "easy"
  | "hard"
  | "very_fast"
  | "progressive"
  | "unknown";

export type WorkoutType = "speed" | "endurance" | "recovery" | "race_day";

export type WorkoutSubtype =
  | "track"
  | "hills"
  | "fartlek"
  | "tempo"
  | "progressive_run"
  | "strength"
  | "marathon"
  | "easy_run"
  | "recovery_run"
  | "unknown";

export interface SourceTrace {
  page_numbers: number[];
  raw_text: string;
}

export interface PaceTableRow {
  row_index: number;
  best_km_pace: string;
  best_km_pace_seconds_per_km: number;
  best_5k_result: string;
  best_5k_result_seconds: number;
  best_5k_pace: string;
  best_5k_pace_seconds_per_km: number;
  best_10k_result: string;
  best_10k_result_seconds: number;
  best_10k_pace: string;
  best_10k_pace_seconds_per_km: number;
  threshold_pace: string;
  threshold_pace_seconds_per_km: number;
  best_half_result: string;
  best_half_result_seconds: number;
  best_half_pace: string;
  best_half_pace_seconds_per_km: number;
  best_marathon_result: string;
  best_marathon_result_seconds: number;
  best_marathon_pace: string;
  best_marathon_pace_seconds_per_km: number;
  recovery_pace: string;
  recovery_pace_seconds_per_km: number;
  source: SourceTrace;
}

export interface Segment {
  order: number;
  distance_meters: number | null;
  distance_km: number | null;
  duration_seconds: number | null;
  repetitions: number;
  pace_type: PaceType;
  recovery_seconds: number | null;
  instructions: string;
}

export interface Workout {
  id: string;
  workout_type: WorkoutType;
  subtype: WorkoutSubtype;
  title: string;
  description: string;
  segments: Segment[];
  recovery_between_segments: string | null;
  target_distance_km_min: number | null;
  target_distance_km_max: number | null;
  target_pace_type: PaceType;
  notes: string[];
  source: SourceTrace;
}

export interface WeekPlan {
  week_number: number;
  weeks_to_race: number;
  headline: string;
  summary: string;
  workouts: Workout[];
  recovery_guidance: string[];
  long_run: Workout | null;
  tags: string[];
  source_pages: number[];
  raw_snippet: string;
}

export interface ScheduleDayEntry {
  label: string;
  workout_ref: string | null;
  workout_type: WorkoutType | null;
  subtype: WorkoutSubtype | null;
}

export interface SampleScheduleRow {
  week_number: number;
  weeks_to_race: number;
  monday: ScheduleDayEntry;
  tuesday: ScheduleDayEntry;
  wednesday: ScheduleDayEntry;
  thursday: ScheduleDayEntry;
  friday: ScheduleDayEntry;
  saturday: ScheduleDayEntry;
  sunday: ScheduleDayEntry;
  source: SourceTrace;
}

export interface GuidanceAdvice {
  title: string;
  text: string;
  source: SourceTrace;
}

export interface IntroSections {
  introduction_text: string;
  weekly_training_explanation: string;
  pace_guidance_text: string;
  pace_examples_text: string;
  weekly_overview_text: string;
  if_you_advice: GuidanceAdvice[];
}

export interface GlossaryTerm {
  term: string;
  category: string;
  description: string;
  source: SourceTrace;
}

export interface DetectedSection {
  name: string;
  page_start: number;
  page_end: number;
  page_numbers: number[];
}

export interface DocumentMetadata {
  title: string;
  language: string;
  source_file: string;
  total_pages: number;
  detected_sections: DetectedSection[];
}

export interface TrainingPlanDocument {
  metadata: DocumentMetadata;
  intro: IntroSections;
  glossary: GlossaryTerm[];
  pace_table: PaceTableRow[];
  weeks: WeekPlan[];
  sample_schedule: SampleScheduleRow[];
}
