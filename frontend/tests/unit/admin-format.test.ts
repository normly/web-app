// frontend/tests/unit/admin-format.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { formatDate, formatLastLogin, formatNumber } from "@/lib/admin-format";

const t = (key: string) =>
  ({ "admin.never": "noch nie", "admin.today": "heute {time}", "admin.yesterday": "gestern {time}" })[key] ?? key;

describe("admin formatting", () => {
  const now = new Date("2026-10-31T12:00:00");

  it("formats numbers per locale", () => {
    expect(formatNumber(1284, "de")).toBe("1.284");
    expect(formatNumber(1284, "en")).toBe("1,284");
  });

  it("shows today and yesterday relatively, older dates absolutely", () => {
    expect(formatLastLogin(null, "de", t, now)).toBe("noch nie");
    expect(formatLastLogin(new Date("2026-10-31T09:12:00").toISOString(), "de", t, now))
      .toBe("heute 09:12");
    expect(formatLastLogin(new Date("2026-10-30T22:40:00").toISOString(), "de", t, now))
      .toBe("gestern 22:40");
    expect(formatLastLogin(new Date("2026-10-19T16:41:00").toISOString(), "de", t, now))
      .toBe("19.10.2026 16:41");
    expect(formatDate(new Date("2026-03-15T10:00:00").toISOString(), "de")).toBe("15.03.2026");
  });
});
