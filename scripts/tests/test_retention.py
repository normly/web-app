# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "retention", Path(__file__).parents[1] / "normly-backup-retention.py"
)
retention = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retention)


def daily(day, hour="033000"):
    return f"2026{day}T{hour}Z-daily.dump.age"


def test_keeps_seven_dailies_one_per_day():
    names = [daily(f"10{d:02d}") for d in range(1, 11)]  # 10 days in October
    deleted = retention.select_deletions(names)
    # days 4..10 are the seven newest; October's monthly anchor is day 10,
    # which is already kept
    assert sorted(deleted) == [
        "20261001T033000Z-daily", "20261002T033000Z-daily", "20261003T033000Z-daily",
    ]


def test_second_daily_on_same_day_is_dropped_first():
    names = [daily("1010", "033000"), daily("1010", "153000")]
    assert retention.select_deletions(names) == ["20261010T033000Z-daily"]


def test_keeps_newest_daily_of_two_most_recent_months():
    recent = [daily(f"10{d:02d}") for d in range(1, 11)]  # fills the 7 daily slots
    names = [daily("0815"), daily("0831"), daily("0930"), *recent]
    deleted = set(retention.select_deletions(names))
    # September's newest (0930) stays as the second monthly anchor; August goes,
    # as do the three oldest October dailies outside the 7 daily slots
    assert deleted == {
        "20260815T033000Z-daily", "20260831T033000Z-daily",
        "20261001T033000Z-daily", "20261002T033000Z-daily", "20261003T033000Z-daily",
    }


def test_keeps_three_newest_pre_rollout_dumps():
    names = [f"2026100{d}T100000Z-pre-0.1.{d}.dump.age" for d in range(1, 6)]
    deleted = set(retention.select_deletions(names))
    assert deleted == {"20261001T100000Z-pre-0.1.1", "20261002T100000Z-pre-0.1.2"}


def test_ignores_unrelated_names():
    assert retention.select_deletions(["notes.txt", "x.dump.age"]) == []
