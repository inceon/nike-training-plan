import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  Dialog,
  Flex,
  Heading,
  Separator,
  Text,
  TextField,
} from "@radix-ui/themes";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  DownloadIcon,
  GearIcon,
  ResetIcon,
} from "@radix-ui/react-icons";
import { documentData } from "./data";
import {
  PACE_PROFILE_LABELS,
  findNearestRow,
  formatDuration,
  profileFromRow,
  resolvePaceLabel,
  summarizeSegment,
  summarizeWorkoutPace,
  type PaceProfile,
  type PaceProfileKey,
} from "./pace";
import type { PaceTableRow, SampleScheduleRow, ScheduleDayEntry, WeekPlan, Workout } from "./types";

const plan = documentData;

type DayKey = "monday" | "tuesday" | "wednesday" | "thursday" | "friday" | "saturday" | "sunday";
type DragPayload = {
  workoutId: string;
  sourceDay: DayKey | null;
};
type WeekAssignmentState = Record<DayKey, string | null>;
type AssignmentOverrides = Record<number, Partial<WeekAssignmentState>>;

const dayKeys: DayKey[] = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];

const dayLabels: Record<DayKey, string> = {
  monday: "Понеділок",
  tuesday: "Вівторок",
  wednesday: "Середа",
  thursday: "Четвер",
  friday: "Пʼятниця",
  saturday: "Субота",
  sunday: "Неділя",
};

const dayShortLabels: Record<DayKey, string> = {
  monday: "Пн",
  tuesday: "Вт",
  wednesday: "Ср",
  thursday: "Чт",
  friday: "Пт",
  saturday: "Сб",
  sunday: "Нд",
};

const initialRow = (() => {
  const row = plan.pace_table[6] ?? plan.pace_table[0];
  if (!row) {
    throw new Error("Pace table data is required for the frontend.");
  }
  return row;
})();

const initialWeek = (() => {
  const week = plan.weeks[0];
  if (!week) {
    throw new Error("Week data is required for the frontend.");
  }
  return week;
})();

const STORAGE_KEY = "nike-training-plan.calendar-assignments.v1";

export default function App() {
  const [selectedRowIndex, setSelectedRowIndex] = useState(initialRow.row_index);
  const [paceProfile, setPaceProfile] = useState<PaceProfile>(() => profileFromRow(initialRow));
  const [selectedWeek, setSelectedWeek] = useState<WeekPlan>(initialWeek);
  const [selectedDay, setSelectedDay] = useState<DayKey>("monday");
  const [weekFilter, setWeekFilter] = useState("");
  const [paceDialogOpen, setPaceDialogOpen] = useState(false);
  const [assignmentOverrides, setAssignmentOverrides] = useState<AssignmentOverrides>(() => loadAssignments());
  const [dragState, setDragState] = useState<DragPayload | null>(null);

  const deferredFilter = useDeferredValue(weekFilter);
  const recommendedRow = useMemo(() => findNearestRow(plan.pace_table, paceProfile), [paceProfile]);
  const selectedWeekIndex = useMemo(
    () => plan.weeks.findIndex((week) => week.week_number === selectedWeek.week_number),
    [selectedWeek.week_number],
  );
  const selectedSchedule = useMemo(
    () => plan.sample_schedule.find((row) => row.week_number === selectedWeek.week_number) ?? null,
    [selectedWeek.week_number],
  );
  const selectedWeekPreviewSrc = useMemo(
    () => `/week-previews/week-${String(selectedWeek.week_number).padStart(2, "0")}-page-${selectedWeek.source_pages[0]}.png`,
    [selectedWeek.week_number, selectedWeek.source_pages],
  );
  const defaultAssignments = useMemo(
    () => buildDefaultAssignments(selectedWeek, selectedSchedule),
    [selectedSchedule, selectedWeek],
  );
  const currentAssignments = useMemo(
    () => mergeAssignments(defaultAssignments, assignmentOverrides[selectedWeek.week_number]),
    [assignmentOverrides, defaultAssignments, selectedWeek.week_number],
  );
  const visibleWeeks = useMemo(() => {
    const needle = deferredFilter.trim().toLowerCase();
    if (!needle) {
      return plan.weeks;
    }
    return plan.weeks.filter((week) =>
      `${week.headline} ${week.summary} ${week.tags.join(" ")}`.toLowerCase().includes(needle),
    );
  }, [deferredFilter]);
  const dayColumns = useMemo(
    () =>
      dayKeys.map((dayKey) => {
        const entry = selectedSchedule?.[dayKey] ?? null;
        const assignedWorkoutId = currentAssignments[dayKey];
        return {
          dayKey,
          entry,
          workout: assignedWorkoutId ? selectedWeek.workouts.find((workout) => workout.id === assignedWorkoutId) ?? null : null,
          isOverride: currentAssignments[dayKey] !== defaultAssignments[dayKey],
        };
      }),
    [currentAssignments, defaultAssignments, selectedSchedule, selectedWeek],
  );
  const selectedDayColumn = useMemo(
    () => dayColumns.find((column) => column.dayKey === selectedDay) ?? dayColumns[0] ?? null,
    [dayColumns, selectedDay],
  );
  const assignedWorkoutIds = useMemo(
    () => new Set(dayKeys.map((dayKey) => currentAssignments[dayKey]).filter((value): value is string => Boolean(value))),
    [currentAssignments],
  );
  const exportPayload = useMemo(
    () => buildCalendarExport(plan.weeks, plan.sample_schedule, assignmentOverrides, paceProfile, recommendedRow.row_index),
    [assignmentOverrides, paceProfile, recommendedRow.row_index],
  );
  const hasWeekOverrides = Object.keys(assignmentOverrides[selectedWeek.week_number] ?? {}).length > 0;

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(assignmentOverrides));
  }, [assignmentOverrides]);

  useEffect(() => {
    const preferredDay = findFirstAssignedDay(currentAssignments) ?? "monday";
    setSelectedDay(preferredDay);
  }, [currentAssignments, selectedWeek.week_number]);

  function selectWeek(week: WeekPlan) {
    startTransition(() => {
      setSelectedWeek(week);
    });
  }

  function moveWeek(direction: -1 | 1) {
    const nextWeek = plan.weeks[selectedWeekIndex + direction];
    if (nextWeek) {
      selectWeek(nextWeek);
    }
  }

  function handleRowSelect(row: PaceTableRow) {
    setSelectedRowIndex(row.row_index);
    setPaceProfile(profileFromRow(row));
  }

  function updatePace(key: PaceProfileKey, value: string) {
    setPaceProfile((current) => ({ ...current, [key]: value }));
  }

  function assignWorkout(targetDay: DayKey, payload: DragPayload) {
    setAssignmentOverrides((current) => {
      const weekNumber = selectedWeek.week_number;
      const merged = mergeAssignments(defaultAssignments, current[weekNumber]);
      const nextWeekAssignments: WeekAssignmentState = { ...merged };
      const targetWorkoutId = nextWeekAssignments[targetDay];

      for (const dayKey of dayKeys) {
        if (nextWeekAssignments[dayKey] === payload.workoutId) {
          nextWeekAssignments[dayKey] = null;
        }
      }

      nextWeekAssignments[targetDay] = payload.workoutId;

      if (payload.sourceDay && payload.sourceDay !== targetDay) {
        nextWeekAssignments[payload.sourceDay] = targetWorkoutId ?? null;
      }

      return {
        ...current,
        [weekNumber]: diffAssignments(defaultAssignments, nextWeekAssignments),
      };
    });
    setSelectedDay(targetDay);
    setDragState(null);
  }

  function resetWeekAssignments() {
    setAssignmentOverrides((current) => {
      const next = { ...current };
      delete next[selectedWeek.week_number];
      return next;
    });
    setDragState(null);
  }

  function exportCalendarJson() {
    const fileName = `training-calendar-export-${formatFileDate(new Date())}.json`;
    downloadJson(fileName, exportPayload);
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.95),_transparent_35%),linear-gradient(180deg,_#fcfbf8,_#f5f1e8)]">
      <div className="mx-auto flex max-w-[1560px] flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 rounded-3xl border border-stone-200 bg-white/85 p-5 shadow-sm backdrop-blur sm:p-6 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-2xl">
            <Text size="1" weight="medium" className="uppercase tracking-[0.18em] text-stone-500">
              Nike Marathon Planner
            </Text>
            <Heading size="8" className="mt-2 max-w-xl text-balance text-stone-950">
              Календар підготовки без зайвого шуму
            </Heading>
            <Text size="3" className="mt-3 max-w-2xl text-stone-600">
              Tailwind для layout, Radix Themes для базових контролів. Тижні, темп і перепризначення залишаються,
              але інтерфейс спрощено.
            </Text>
          </div>

          <div className="flex flex-wrap items-center gap-2 xl:justify-end">
            <Button variant="soft" color="gray" onClick={() => moveWeek(-1)} disabled={selectedWeekIndex <= 0}>
              <ChevronLeftIcon />
              Назад
            </Button>
            <div className="min-w-[140px] rounded-2xl border border-stone-200 bg-stone-50 px-4 py-2 text-center">
              <Text size="1" className="uppercase tracking-[0.14em] text-stone-500">
                Тиждень {selectedWeek.week_number}
              </Text>
              <Text size="2" weight="medium" className="block text-stone-900">
                {selectedWeek.weeks_to_race} до старту
              </Text>
            </div>
            <Button variant="soft" color="gray" onClick={() => moveWeek(1)} disabled={selectedWeekIndex >= plan.weeks.length - 1}>
              Далі
              <ChevronRightIcon />
            </Button>
            <Button variant="soft" color="gray" onClick={exportCalendarJson}>
              <DownloadIcon />
              Експорт JSON
            </Button>
            <Dialog.Root open={paceDialogOpen} onOpenChange={setPaceDialogOpen}>
              <Dialog.Trigger>
                <Button>
                  <GearIcon />
                  Темп
                </Button>
              </Dialog.Trigger>
              <Dialog.Content className="max-w-xl">
                <Flex direction="column" gap="4">
                  <div>
                    <Dialog.Title>Налаштування темпу</Dialog.Title>
                    <Dialog.Description>
                      Оберіть рядок таблиці або відкоригуйте значення вручну.
                    </Dialog.Description>
                  </div>

                  <label className="grid gap-2">
                    <Text size="2" weight="medium">
                      Базовий рядок
                    </Text>
                    <select
                      className="h-10 rounded-xl border border-stone-300 bg-white px-3 text-sm text-stone-900 outline-none"
                      value={selectedRowIndex}
                      onChange={(event) => {
                        const row = plan.pace_table.find((item) => item.row_index === Number(event.target.value));
                        if (row) {
                          handleRowSelect(row);
                        }
                      }}
                    >
                      {plan.pace_table.map((row) => (
                        <option key={row.row_index} value={row.row_index}>
                          #{row.row_index} · 5K {row.best_5k_result} · recovery {row.recovery_pace}
                        </option>
                      ))}
                    </select>
                  </label>

                  <div className="grid gap-3 sm:grid-cols-2">
                    {(Object.keys(PACE_PROFILE_LABELS) as PaceProfileKey[]).map((key) => (
                      <label key={key} className="grid gap-2">
                        <Text size="2" weight="medium">
                          {translatePaceLabel(PACE_PROFILE_LABELS[key])}
                        </Text>
                        <TextField.Root
                          value={paceProfile[key]}
                          onChange={(event) => updatePace(key, event.target.value)}
                          className="w-full"
                        />
                      </label>
                    ))}
                  </div>

                  <Card>
                    <Flex direction="column" gap="2">
                      <Text size="1" className="uppercase tracking-[0.14em] text-stone-500">
                        Найближчий профіль
                      </Text>
                      <Heading size="4">Рядок {recommendedRow.row_index}</Heading>
                      <Text size="2" className="text-stone-600">
                        5K {recommendedRow.best_5k_result} · 10K {recommendedRow.best_10k_result} · марафон{" "}
                        {recommendedRow.best_marathon_result}
                      </Text>
                    </Flex>
                  </Card>

                  <Flex justify="between" gap="3">
                    <Button variant="soft" color="gray" onClick={() => handleRowSelect(recommendedRow)}>
                      Застосувати рекомендований
                    </Button>
                    <Dialog.Close>
                      <Button>Готово</Button>
                    </Dialog.Close>
                  </Flex>
                </Flex>
              </Dialog.Content>
            </Dialog.Root>
          </div>
        </header>

        <Card className="rounded-3xl">
          <div className="flex flex-col gap-4 p-5 sm:p-6">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <Text size="1" className="uppercase tracking-[0.18em] text-stone-500">
                  Навігація планом
                </Text>
                <Heading size="5" className="mt-1">
                  Усі 18 тижнів
                </Heading>
              </div>
              <div className="w-full max-w-md">
                <TextField.Root
                  placeholder="Пошук за фазою, тегом або заголовком"
                  value={weekFilter}
                  onChange={(event) => setWeekFilter(event.target.value)}
                />
              </div>
            </div>

            <div className="scrollbar-none overflow-x-auto pb-1">
              <div className="flex min-w-max gap-3">
                {visibleWeeks.map((week) => {
                  const active = week.week_number === selectedWeek.week_number;
                  return (
                    <button
                      key={week.week_number}
                      type="button"
                      onClick={() => selectWeek(week)}
                      className={`w-56 rounded-2xl border px-4 py-3 text-left transition ${
                        active
                          ? "border-stone-900 bg-stone-900 text-white"
                          : "border-stone-200 bg-stone-50 text-stone-900 hover:border-stone-300 hover:bg-white"
                      }`}
                    >
                      <div className="text-[11px] uppercase tracking-[0.18em] opacity-70">Тиждень {week.week_number}</div>
                      <div className="mt-2 line-clamp-2 text-sm font-semibold">{week.headline}</div>
                      <div className="mt-2 text-xs opacity-75">{week.weeks_to_race} до старту</div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </Card>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="flex flex-col gap-5">
            <Card className="rounded-3xl">
              <div className="flex flex-col gap-5 p-5 sm:p-6">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <Text size="1" className="uppercase tracking-[0.18em] text-stone-500">
                      Weekly board
                    </Text>
                    <Heading size="6" className="mt-1">
                      {selectedWeek.headline}
                    </Heading>
                    <Text size="3" className="mt-2 max-w-3xl text-stone-600">
                      {selectedWeek.summary}
                    </Text>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <StatBadge label="Тренувань" value={String(selectedWeek.workouts.length)} />
                    <StatBadge
                      label="Довгий забіг"
                      value={selectedWeek.long_run ? formatDistanceRange(selectedWeek.long_run) : "Race week"}
                    />
                    <StatBadge label="Темп" value={`#${recommendedRow.row_index}`} />
                  </div>
                </div>

                <div className="flex flex-col gap-3 rounded-2xl border border-dashed border-stone-300 bg-stone-50 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <Text size="2" className="text-stone-600">
                    Перетягуйте сесії між днями. Зміни зберігаються локально.
                  </Text>
                  <Button variant="soft" color="gray" onClick={resetWeekAssignments} disabled={!hasWeekOverrides}>
                    <ResetIcon />
                    Скинути тиждень
                  </Button>
                </div>

                <div className="scrollbar-none overflow-x-auto pb-2">
                  <div className="grid min-w-[1540px] grid-cols-7 gap-3">
                    {dayColumns.map(({ dayKey, entry, workout, isOverride }) => (
                      <DayColumn
                        key={dayKey}
                        dayKey={dayKey}
                        entry={entry}
                        workout={workout}
                        paceProfile={paceProfile}
                        isLongRun={Boolean(selectedWeek.long_run && workout?.id === selectedWeek.long_run.id)}
                        isOverride={isOverride}
                        isSelected={selectedDay === dayKey}
                        isDragTarget={dragState !== null}
                        onSelectDay={setSelectedDay}
                        onDragStart={setDragState}
                        onDropWorkout={assignWorkout}
                        onDragEnd={() => setDragState(null)}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </Card>

            <Card className="rounded-3xl">
              <div className="flex flex-col gap-5 p-5 sm:p-6">
                <div className="flex flex-col gap-2">
                  <Text size="1" className="uppercase tracking-[0.18em] text-stone-500">
                    Assignments
                  </Text>
                  <Heading size="5">Деталі вибраного дня</Heading>
                  <Text size="2" className="text-stone-600">
                    Без повторного списку всіх тренувань. Унизу тільки повна деталізація активного дня.
                  </Text>
                </div>

                <div className="flex flex-col gap-4">
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                      <Text size="1" className="uppercase tracking-[0.18em] text-stone-500">
                        Selected day
                      </Text>
                      <Heading size="4" className="mt-1">
                        {selectedDayColumn ? dayLabels[selectedDayColumn.dayKey] : "День не вибрано"}
                      </Heading>
                    </div>
                    <Text size="2" className="text-stone-500">
                      {selectedDayColumn?.entry?.label ?? "Немає слоту в матриці"}
                    </Text>
                  </div>

                  {selectedDayColumn?.workout ? (
                    <WorkoutDetailCard
                      workout={selectedDayColumn.workout}
                      paceProfile={paceProfile}
                      assignmentDay={selectedDayColumn.dayKey}
                    />
                  ) : (
                    <div className="rounded-2xl border border-dashed border-stone-300 bg-stone-50 px-4 py-5 text-sm text-stone-600">
                      Для цього дня зараз немає призначеного тренування. Можна перетягнути сесію з іншого дня.
                    </div>
                  )}
                </div>
              </div>
            </Card>
          </div>

          <aside className="flex flex-col gap-5">
            <Card className="rounded-3xl">
              <div className="flex flex-col gap-4 p-5">
                <div>
                  <Text size="1" className="uppercase tracking-[0.18em] text-stone-500">
                    PDF source
                  </Text>
                  <Heading size="4" className="mt-1">
                    Оригінальна сторінка
                  </Heading>
                </div>
                <Dialog.Root>
                  <Dialog.Trigger>
                    <button
                      type="button"
                      className="overflow-hidden rounded-2xl border border-stone-200 bg-stone-50 transition hover:border-stone-300"
                    >
                      <img
                        src={selectedWeekPreviewSrc}
                        alt={`PDF preview for week ${selectedWeek.week_number}`}
                        loading="lazy"
                      />
                    </button>
                  </Dialog.Trigger>
                  <Dialog.Content maxWidth="96vw" className="w-[96vw] max-w-[1400px]">
                    <div className="flex flex-col gap-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <Dialog.Title>Оригінальна сторінка PDF</Dialog.Title>
                          <Dialog.Description>
                            Тиждень {selectedWeek.week_number}, сторінка {selectedWeek.source_pages.join(", ")}
                          </Dialog.Description>
                        </div>
                        <Dialog.Close>
                          <Button variant="soft" color="gray">
                            Закрити
                          </Button>
                        </Dialog.Close>
                      </div>
                      <div className="max-h-[82vh] overflow-auto rounded-2xl border border-stone-200 bg-stone-50 p-2">
                        <img
                          src={selectedWeekPreviewSrc}
                          alt={`PDF preview fullscreen for week ${selectedWeek.week_number}`}
                          className="mx-auto h-auto max-w-full"
                        />
                      </div>
                    </div>
                  </Dialog.Content>
                </Dialog.Root>
              </div>
            </Card>

            <Card className="rounded-3xl">
              <div className="flex flex-col gap-4 p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <Text size="1" className="uppercase tracking-[0.18em] text-stone-500">
                      Pace profile
                    </Text>
                    <Heading size="4" className="mt-1">
                      Поточні значення
                    </Heading>
                  </div>
                  <Button variant="soft" color="gray" onClick={() => setPaceDialogOpen(true)}>
                    <GearIcon />
                    Змінити
                  </Button>
                </div>

                <div className="grid gap-2">
                  {(Object.keys(PACE_PROFILE_LABELS) as PaceProfileKey[]).map((key) => (
                    <div key={key} className="flex items-center justify-between rounded-2xl border border-stone-200 bg-stone-50 px-3 py-2">
                      <Text size="2" className="text-stone-600">
                        {translatePaceLabel(PACE_PROFILE_LABELS[key])}
                      </Text>
                      <Text size="2" weight="medium">
                        {paceProfile[key]}
                      </Text>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          </aside>
        </div>
      </div>
    </div>
  );
}

function StatBadge({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-stone-50 px-3 py-2">
      <Text size="1" className="uppercase tracking-[0.14em] text-stone-500">
        {label}
      </Text>
      <Text size="2" weight="medium" className="block text-stone-900">
        {value}
      </Text>
    </div>
  );
}

function DayColumn({
  dayKey,
  entry,
  workout,
  paceProfile,
  isLongRun,
  isOverride,
  isSelected,
  isDragTarget,
  onSelectDay,
  onDragStart,
  onDropWorkout,
  onDragEnd,
}: {
  dayKey: DayKey;
  entry: ScheduleDayEntry | null;
  workout: Workout | null;
  paceProfile: PaceProfile;
  isLongRun: boolean;
  isOverride: boolean;
  isSelected: boolean;
  isDragTarget: boolean;
  onSelectDay: (day: DayKey) => void;
  onDragStart: (payload: DragPayload | null) => void;
  onDropWorkout: (targetDay: DayKey, payload: DragPayload) => void;
  onDragEnd: () => void;
}) {
  const projectedPace = workout ? summarizeWorkoutPace(workout, paceProfile) : null;

  return (
    <button
      type="button"
      onClick={() => onSelectDay(dayKey)}
      className={`flex min-h-[320px] flex-col gap-3 rounded-3xl border p-4 text-left transition ${
        isSelected
          ? "border-stone-900 bg-white shadow-sm"
          : "border-stone-200 bg-stone-50 hover:border-stone-300 hover:bg-white"
      } ${isOverride ? "ring-1 ring-stone-300" : ""} ${isDragTarget ? "border-dashed" : ""}`}
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        const payload = readDragPayload(event.dataTransfer.getData("text/plain"));
        if (payload) {
          onDropWorkout(dayKey, payload);
        }
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-stone-500">{dayShortLabels[dayKey]}</div>
          <div className="mt-1 text-sm font-semibold text-stone-900">{dayLabels[dayKey]}</div>
        </div>
        <div className="flex flex-col items-end gap-1">
          {isOverride ? <Badge variant="soft" color="gray">custom</Badge> : null}
          {isLongRun ? <Badge variant="soft" color="brown">long</Badge> : null}
        </div>
      </div>

      <Text size="1" className="text-stone-500">
        {entry?.label ?? "Немає слоту в матриці"}
      </Text>

      {workout ? (
        <div
          className="flex flex-1 cursor-grab flex-col gap-3"
          draggable
          onDragStart={(event) => {
            const payload = { workoutId: workout.id, sourceDay: dayKey };
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData("text/plain", JSON.stringify(payload));
            onDragStart(payload);
          }}
          onDragEnd={onDragEnd}
        >
          <div>
            <Heading size="3" className="leading-snug">
              {workout.title}
            </Heading>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge variant="soft" color="gray">
              {humanize(workout.subtype)}
            </Badge>
            <Badge variant="soft" color="gray">
              {formatDistanceRange(workout)}
            </Badge>
            {projectedPace ? <Badge variant="soft">{projectedPace}</Badge> : null}
          </div>
        </div>
      ) : (
        <div className="mt-auto rounded-2xl border border-dashed border-stone-300 bg-white/70 px-3 py-4 text-sm text-stone-500">
          Порожній слот
        </div>
      )}
    </button>
  );
}

function WorkoutDetailCard({
  workout,
  paceProfile,
  assignmentDay,
}: {
  workout: Workout;
  paceProfile: PaceProfile;
  assignmentDay: DayKey | null;
}) {
  const projectedPace = summarizeWorkoutPace(workout, paceProfile);
  return (
    <Card className="rounded-3xl">
      <div className="flex flex-col gap-4 p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <Text size="1" className="uppercase tracking-[0.18em] text-stone-500">
              {humanize(workout.workout_type)}
            </Text>
            <Heading size="5" className="mt-1">
              {workout.title}
            </Heading>
          </div>
          <div className="flex flex-wrap gap-2">
            {assignmentDay ? <Badge variant="soft" color="gray">{dayLabels[assignmentDay]}</Badge> : null}
            <Badge variant="soft" color="gray">
              {humanize(workout.subtype)}
            </Badge>
            <Badge variant="soft" color="gray">
              {formatDistanceRange(workout)}
            </Badge>
            {projectedPace ? <Badge variant="soft">{projectedPace}</Badge> : null}
          </div>
        </div>

        <Text size="3" className="text-stone-600">
          {workout.description}
        </Text>

        {workout.segments.length > 0 ? (
          <div className="grid gap-3">
            {workout.segments.map((segment) => (
              <div key={`${workout.id}-${segment.order}-${segment.instructions}`} className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3">
                <div className="text-sm font-semibold text-stone-900">{summarizeSegment(segment, paceProfile)}</div>
                <div className="mt-1 text-sm text-stone-600">{segment.instructions}</div>
                {segment.recovery_seconds ? (
                  <div className="mt-2 text-xs uppercase tracking-[0.14em] text-stone-500">
                    Відновлення {formatDuration(segment.recovery_seconds)}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}

        {workout.recovery_between_segments ? (
          <div className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3">
            <Text size="1" className="uppercase tracking-[0.14em] text-stone-500">
              Між відрізками
            </Text>
            <Text size="2" className="mt-1 text-stone-600">
              {workout.recovery_between_segments}
            </Text>
          </div>
        ) : null}

        {workout.notes.length > 0 ? (
          <div className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3">
            <Text size="1" className="uppercase tracking-[0.14em] text-stone-500">
              Нотатки
            </Text>
            <Text size="2" className="mt-1 text-stone-600">
              {workout.notes.join(" ")}
            </Text>
          </div>
        ) : null}

        <div className="flex items-center justify-between gap-3 border-t border-stone-200 pt-3 text-sm text-stone-500">
          <span>Сторінка {workout.source.page_numbers.join(", ")}</span>
          {resolvePaceLabel(workout.target_pace_type, paceProfile) ? (
            <span>{resolvePaceLabel(workout.target_pace_type, paceProfile)}</span>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

function matchScheduleWorkout(week: WeekPlan, entry: ScheduleDayEntry): Workout | null {
  if (entry.workout_ref) {
    const exactMatch = week.workouts.find((workout) => workout.id === entry.workout_ref);
    if (exactMatch) {
      return exactMatch;
    }
  }

  const normalizedLabel = normalizeText(entry.label);
  const titleMatch = week.workouts.find((workout) => normalizeText(workout.title) === normalizedLabel);
  if (titleMatch) {
    return titleMatch;
  }

  if (entry.subtype) {
    const subtypeMatch = week.workouts.find((workout) => workout.subtype === entry.subtype);
    if (subtypeMatch) {
      return subtypeMatch;
    }
  }

  if (entry.workout_type) {
    const typeMatch = week.workouts.find((workout) => workout.workout_type === entry.workout_type);
    if (typeMatch) {
      return typeMatch;
    }
  }

  return null;
}

function buildDefaultAssignments(week: WeekPlan, schedule: SampleScheduleRow | null): WeekAssignmentState {
  const assignments = emptyAssignments();

  for (const dayKey of dayKeys) {
    const entry = schedule?.[dayKey];
    assignments[dayKey] = entry ? matchScheduleWorkout(week, entry)?.id ?? null : null;
  }

  return assignments;
}

function emptyAssignments(): WeekAssignmentState {
  return {
    monday: null,
    tuesday: null,
    wednesday: null,
    thursday: null,
    friday: null,
    saturday: null,
    sunday: null,
  };
}

function mergeAssignments(defaults: WeekAssignmentState, override: Partial<WeekAssignmentState> | undefined): WeekAssignmentState {
  return { ...defaults, ...override };
}

function diffAssignments(defaults: WeekAssignmentState, next: WeekAssignmentState): Partial<WeekAssignmentState> {
  const diff: Partial<WeekAssignmentState> = {};
  for (const dayKey of dayKeys) {
    if (defaults[dayKey] !== next[dayKey]) {
      diff[dayKey] = next[dayKey];
    }
  }
  return diff;
}

function loadAssignments(): AssignmentOverrides {
  if (typeof window === "undefined") {
    return {};
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw);
    return typeof parsed === "object" && parsed !== null ? parsed : {};
  } catch {
    return {};
  }
}

function readDragPayload(raw: string): DragPayload | null {
  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed?.workoutId === "string" && (parsed.sourceDay === null || typeof parsed.sourceDay === "string")) {
      return parsed as DragPayload;
    }
  } catch {
    return null;
  }
  return null;
}

function findFirstAssignedDay(assignments: WeekAssignmentState): DayKey | null {
  for (const dayKey of dayKeys) {
    if (assignments[dayKey]) {
      return dayKey;
    }
  }
  return null;
}

function buildCalendarExport(
  weeks: WeekPlan[],
  schedules: SampleScheduleRow[],
  assignmentOverrides: AssignmentOverrides,
  paceProfile: PaceProfile,
  recommendedRowIndex: number,
) {
  const resolvedWeeks = weeks.map((week) => {
    const schedule = schedules.find((row) => row.week_number === week.week_number) ?? null;
    const defaultAssignments = buildDefaultAssignments(week, schedule);
    const resolvedAssignments = mergeAssignments(defaultAssignments, assignmentOverrides[week.week_number]);

    const days = dayKeys.map((dayKey) => {
      const scheduleEntry = schedule?.[dayKey] ?? null;
      const assignedWorkoutId = resolvedAssignments[dayKey];
      const assignedWorkout = assignedWorkoutId
        ? week.workouts.find((workout) => workout.id === assignedWorkoutId) ?? null
        : null;
      const defaultWorkoutId = defaultAssignments[dayKey];

      return {
        day_key: dayKey,
        day_label: dayLabels[dayKey],
        matrix_label: scheduleEntry?.label ?? null,
        source_workout_ref: scheduleEntry?.workout_ref ?? null,
        source_workout_id: defaultWorkoutId,
        assigned_workout_id: assignedWorkout?.id ?? null,
        assigned_workout_title: assignedWorkout?.title ?? null,
        workout_type: assignedWorkout?.workout_type ?? scheduleEntry?.workout_type ?? null,
        subtype: assignedWorkout?.subtype ?? scheduleEntry?.subtype ?? null,
        target_pace: assignedWorkout ? summarizeWorkoutPace(assignedWorkout, paceProfile) : null,
        overridden: defaultWorkoutId !== resolvedAssignments[dayKey],
      };
    });

    const assignedIds = new Set(days.map((day) => day.assigned_workout_id).filter((value): value is string => Boolean(value)));
    const unassignedWorkouts = week.workouts
      .filter((workout) => !assignedIds.has(workout.id))
      .map((workout) => ({
        workout_id: workout.id,
        title: workout.title,
        workout_type: workout.workout_type,
        subtype: workout.subtype,
        target_pace: summarizeWorkoutPace(workout, paceProfile),
      }));

    return {
      week_number: week.week_number,
      weeks_to_race: week.weeks_to_race,
      headline: week.headline,
      source_pages: week.source_pages,
      has_overrides: Object.keys(assignmentOverrides[week.week_number] ?? {}).length > 0,
      days,
      unassigned_workouts: unassignedWorkouts,
    };
  });

  return {
    export_version: 1,
    exported_at: new Date().toISOString(),
    source_document: {
      title: plan.metadata.title,
      language: plan.metadata.language,
      source_file: plan.metadata.source_file,
      total_pages: plan.metadata.total_pages,
    },
    selected_pace_profile: {
      recommended_row_index: recommendedRowIndex,
      values: paceProfile,
    },
    customization_summary: {
      customized_weeks: resolvedWeeks.filter((week) => week.has_overrides).length,
      total_weeks: resolvedWeeks.length,
    },
    weeks: resolvedWeeks,
  };
}

function formatFileDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  const hours = String(value.getHours()).padStart(2, "0");
  const minutes = String(value.getMinutes()).padStart(2, "0");
  return `${year}${month}${day}-${hours}${minutes}`;
}

function downloadJson(fileName: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  window.URL.revokeObjectURL(url);
}

function normalizeText(value: string): string {
  return value.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
}

function formatDistanceRange(workout: Workout): string {
  if (workout.target_distance_km_min && workout.target_distance_km_max) {
    if (workout.target_distance_km_min === workout.target_distance_km_max) {
      return `${trimKm(workout.target_distance_km_min)} км`;
    }
    return `${trimKm(workout.target_distance_km_min)}-${trimKm(workout.target_distance_km_max)} км`;
  }
  if (workout.segments.length > 0) {
    return `${workout.segments.length} сегментів`;
  }
  return "Вільний обсяг";
}

function trimKm(value: number): string {
  const rounded = Number(value.toFixed(1));
  return Number.isInteger(rounded) ? String(rounded) : rounded.toString();
}

function humanize(value: string): string {
  return value.replace(/_/g, " ");
}

function translatePaceLabel(value: string): string {
  switch (value) {
    case "1K pace":
      return "Темп 1 км";
    case "5K pace":
      return "Темп 5 км";
    case "10K pace":
      return "Темп 10 км";
    case "Threshold":
      return "Пороговий темп";
    case "Half marathon":
      return "Півмарафон";
    case "Marathon":
      return "Марафон";
    case "Recovery":
      return "Відновлення";
    default:
      return value;
  }
}
