// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

const HOUR_MS = 3_600_000;
const DAY_MS = 24 * HOUR_MS;

// Resets are UTC instants; they are shown in the viewer's local time.
export function formatResetTime(resetsAt: string, locale: string, now: Date = new Date()): string {
  const reset = new Date(resetsAt);
  const options: Intl.DateTimeFormatOptions =
    reset.getTime() - now.getTime() < DAY_MS
      ? { hour: "2-digit", minute: "2-digit" }
      : { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" };
  return new Intl.DateTimeFormat(locale, options).format(reset);
}

export function formatRelativeReset(resetsAt: string, locale: string, now: Date = new Date()): string {
  const remaining = new Date(resetsAt).getTime() - now.getTime();
  const format = new Intl.RelativeTimeFormat(locale, { numeric: "always" });
  if (remaining < 2 * DAY_MS) {
    return format.format(Math.max(1, Math.round(remaining / HOUR_MS)), "hour");
  }
  return format.format(Math.round(remaining / DAY_MS), "day");
}
