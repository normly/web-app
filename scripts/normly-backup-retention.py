#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""
Decide which backups to delete. Reads object names (one per line) from stdin,
prints the base names (<timestamp>-<kind>) to delete. Standard library only:
it runs on the VM next to the shell script.

Keep: 7 daily (newest per calendar day), the newest daily of each of the 2 most
recent calendar months, and the 3 newest pre-rollout dumps.
"""

import re
import sys

DAILY_KEEP = 7
MONTHLY_KEEP = 2
PRE_KEEP = 3

_NAME = re.compile(r"^(\d{8})T(\d{6})Z-(daily|pre-[0-9A-Za-z.\-]+)\.dump\.age$")


def select_deletions(names: list[str]) -> list[str]:
    daily, pre = [], []
    for name in names:
        match = _NAME.match(name)
        if not match:
            continue
        date, time, kind = match.groups()
        base = f"{date}T{time}Z-{kind}"
        (daily if kind == "daily" else pre).append((date + time, date, base))

    keep: set[str] = set()

    newest_first = sorted(daily, reverse=True)
    days_seen: list[str] = []
    for _stamp, date, base in newest_first:
        if date in days_seen:
            continue
        days_seen.append(date)
        if len(days_seen) <= DAILY_KEEP:
            keep.add(base)

    months_seen: list[str] = []
    for _stamp, date, base in newest_first:
        month = date[:6]
        if month in months_seen:
            continue
        months_seen.append(month)
        if len(months_seen) <= MONTHLY_KEEP:
            keep.add(base)

    for _stamp, _date, base in sorted(pre, reverse=True)[:PRE_KEEP]:
        keep.add(base)

    return sorted(base for _s, _d, base in daily + pre if base not in keep)


if __name__ == "__main__":
    for base in select_deletions([line.strip() for line in sys.stdin if line.strip()]):
        print(base)
