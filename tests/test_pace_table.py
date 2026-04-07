from __future__ import annotations


def test_pace_table_has_rows(document):
    assert len(document.pace_table) > 0


def test_pace_table_row_is_normalized(document):
    row = document.pace_table[0]
    assert row.best_km_pace_seconds_per_km > 0
    assert row.best_5k_result_seconds > 0
    assert row.best_5k_pace_seconds_per_km > 0
    assert row.best_marathon_result_seconds > row.best_half_result_seconds
