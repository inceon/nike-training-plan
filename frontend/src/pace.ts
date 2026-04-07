import type { PaceTableRow, PaceType, Segment, Workout } from "./types";

export type PaceProfileKey =
  | "km_pace"
  | "pace_5k"
  | "pace_10k"
  | "threshold"
  | "half"
  | "marathon"
  | "recovery";

export interface PaceProfile {
  km_pace: string;
  pace_5k: string;
  pace_10k: string;
  threshold: string;
  half: string;
  marathon: string;
  recovery: string;
}

export const PACE_PROFILE_LABELS: Record<PaceProfileKey, string> = {
  km_pace: "1K pace",
  pace_5k: "5K pace",
  pace_10k: "10K pace",
  threshold: "Threshold",
  half: "Half marathon",
  marathon: "Marathon",
  recovery: "Recovery",
};

export function profileFromRow(row: PaceTableRow): PaceProfile {
  return {
    km_pace: row.best_km_pace,
    pace_5k: row.best_5k_pace,
    pace_10k: row.best_10k_pace,
    threshold: row.threshold_pace,
    half: row.best_half_pace,
    marathon: row.best_marathon_pace,
    recovery: row.recovery_pace,
  };
}

export function resolvePaceLabel(paceType: PaceType, profile: PaceProfile): string | null {
  switch (paceType) {
    case "km_pace":
      return `${profile.km_pace}/km`;
    case "mile_pace":
      return "Mile effort";
    case "pace_5k":
      return `${profile.pace_5k}/km`;
    case "pace_10k":
      return `${profile.pace_10k}/km`;
    case "threshold":
      return `${profile.threshold}/km`;
    case "marathon_pace":
      return `${profile.marathon}/km`;
    case "recovery":
      return `${profile.recovery}/km`;
    case "easy":
      return `${profile.recovery}/km easy`;
    case "hard":
      return "Hard effort";
    case "very_fast":
      return "Very fast";
    case "progressive":
      return "Progressive build";
    case "unknown":
      return null;
  }
}

export function summarizeWorkoutPace(workout: Workout, profile: PaceProfile): string {
  const pace = resolvePaceLabel(workout.target_pace_type, profile);
  if (pace) {
    return pace;
  }
  const firstSegment = workout.segments.find((segment) => resolvePaceLabel(segment.pace_type, profile));
  const segmentPace = firstSegment ? resolvePaceLabel(firstSegment.pace_type, profile) : null;
  return segmentPace ?? "Open pace";
}

export function summarizeSegment(segment: Segment, profile: PaceProfile): string {
  const parts: string[] = [];
  if (segment.repetitions > 1) {
    parts.push(`${segment.repetitions}x`);
  }
  if (segment.distance_meters) {
    parts.push(`${segment.distance_meters} m`);
  } else if (segment.distance_km) {
    parts.push(`${segment.distance_km} km`);
  } else if (segment.duration_seconds) {
    parts.push(formatDuration(segment.duration_seconds));
  }
  const pace = resolvePaceLabel(segment.pace_type, profile);
  if (pace) {
    parts.push(`@ ${pace}`);
  }
  return parts.join(" ");
}

export function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  if (minutes === 0) {
    return `${remaining}s`;
  }
  if (remaining === 0) {
    return `${minutes}m`;
  }
  return `${minutes}m ${remaining}s`;
}

export function parsePaceInput(value: string): number | null {
  const match = value.trim().match(/^(\d+):(\d{2})$/);
  if (!match) {
    return null;
  }
  const minutes = Number(match[1]);
  const seconds = Number(match[2]);
  return minutes * 60 + seconds;
}

export function paceToString(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}:${String(remainder).padStart(2, "0")}`;
}

export function findNearestRow(rows: PaceTableRow[], profile: PaceProfile): PaceTableRow {
  const firstRow = rows[0];
  if (!firstRow) {
    throw new Error("Pace table data is required.");
  }

  const values = {
    km_pace: parsePaceInput(profile.km_pace),
    pace_5k: parsePaceInput(profile.pace_5k),
    pace_10k: parsePaceInput(profile.pace_10k),
    threshold: parsePaceInput(profile.threshold),
    marathon: parsePaceInput(profile.marathon),
    recovery: parsePaceInput(profile.recovery),
  };

  let winner = firstRow;
  let winnerScore = Number.POSITIVE_INFINITY;

  for (const row of rows) {
    const score =
      Math.abs((values.km_pace ?? row.best_km_pace_seconds_per_km) - row.best_km_pace_seconds_per_km) +
      Math.abs((values.pace_5k ?? row.best_5k_pace_seconds_per_km) - row.best_5k_pace_seconds_per_km) +
      Math.abs((values.pace_10k ?? row.best_10k_pace_seconds_per_km) - row.best_10k_pace_seconds_per_km) +
      Math.abs((values.threshold ?? row.threshold_pace_seconds_per_km) - row.threshold_pace_seconds_per_km) +
      Math.abs((values.marathon ?? row.best_marathon_pace_seconds_per_km) - row.best_marathon_pace_seconds_per_km) +
      Math.abs((values.recovery ?? row.recovery_pace_seconds_per_km) - row.recovery_pace_seconds_per_km);
    if (score < winnerScore) {
      winner = row;
      winnerScore = score;
    }
  }

  return winner;
}
