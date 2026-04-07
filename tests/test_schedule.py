from __future__ import annotations


def test_sample_schedule_row_count(document):
    assert len(document.sample_schedule) == 18


def test_schedule_rows_align_with_week_models(document):
    assert [row.week_number for row in document.sample_schedule] == list(range(1, 19))
    assert [row.weeks_to_race for row in document.sample_schedule] == list(range(18, 0, -1))


def test_schedule_maps_core_workouts_when_possible(document):
    first_row = document.sample_schedule[0]
    assert first_row.tuesday.workout_ref is not None
    assert first_row.thursday.workout_ref is not None
    assert first_row.saturday.workout_ref is not None
