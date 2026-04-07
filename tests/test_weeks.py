from __future__ import annotations

from parser.models import WorkoutType


def test_week_count(document):
    assert len(document.weeks) == 18


def test_weeks_are_normalized_in_order(document):
    assert [week.week_number for week in document.weeks] == list(range(1, 19))
    assert [week.weeks_to_race for week in document.weeks] == list(range(18, 0, -1))


def test_long_run_exists_in_each_week(document):
    for week in document.weeks:
        assert week.long_run is not None, f"week {week.week_number} should have a long run or race day"
        assert week.long_run.workout_type in {WorkoutType.ENDURANCE, WorkoutType.RACE_DAY}


def test_recovery_workouts_exist_in_each_week(document):
    for week in document.weeks:
        recovery_workouts = [workout for workout in week.workouts if workout.workout_type == WorkoutType.RECOVERY]
        assert recovery_workouts, f"week {week.week_number} should include recovery workouts"
