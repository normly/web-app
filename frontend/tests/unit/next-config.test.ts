// frontend/tests/unit/next-config.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import nextConfig from "../../next.config";

describe("next config headers", () => {
  it("sends no Referer from pages that carry a one-time token", async () => {
    const rules = await nextConfig.headers!();
    const sources = rules.map((r) => r.source).sort();
    expect(sources).toEqual([
      "/confirm-email-change", "/invitation", "/magic-link", "/reset-password", "/verify-email",
    ]);
    for (const r of rules) {
      expect(r.headers).toContainEqual({ key: "Referrer-Policy", value: "no-referrer" });
    }
  });
});
