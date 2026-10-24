// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { interpolate } from "@/lib/i18n/interpolate";
import { formatRelativeReset, formatResetTime } from "@/lib/reset-time";

const now = new Date("2026-10-22T19:00:00Z");

describe("reset time formatting", () => {
  it("shows only the time for a reset within a day", () => {
    const expected = new Date("2026-10-23T00:00:00Z").toLocaleTimeString("de", {
      hour: "2-digit", minute: "2-digit",
    });
    expect(formatResetTime("2026-10-23T00:00:00Z", "de", now)).toBe(expected);
  });

  it("includes the date for a later reset", () => {
    expect(formatResetTime("2026-11-01T00:00:00Z", "de", now)).toMatch(/November|Okt/);
  });

  it("describes the remaining time in hours, then days", () => {
    expect(formatRelativeReset("2026-10-23T00:00:00Z", "de", now)).toBe("in 5 Stunden");
    expect(formatRelativeReset("2026-11-01T00:00:00Z", "en", now)).toBe("in 9 days");
  });

  it("interpolates placeholders", () => {
    expect(interpolate("{used} von {limit}", { used: "7", limit: "30" })).toBe("7 von 30");
  });
});
