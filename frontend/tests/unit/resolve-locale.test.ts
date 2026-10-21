// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { localeFromRequest, resolveLocale } from "@/lib/i18n/resolve-locale";

describe("resolveLocale", () => {
  it("prefers a valid cookie", () => {
    expect(resolveLocale("en", "de-DE")).toBe("en");
  });

  it("falls back to Accept-Language", () => {
    expect(resolveLocale(undefined, "en-GB,en;q=0.9")).toBe("en");
    expect(resolveLocale("fr", "de-DE")).toBe("de");
  });

  it("defaults to German", () => {
    expect(resolveLocale(undefined, null)).toBe("de");
  });

  it("reads cookie and header from a request", () => {
    const request = new NextRequest("http://localhost/x", {
      headers: { cookie: "normly_locale=en", "accept-language": "de-DE" },
    });
    expect(localeFromRequest(request)).toBe("en");
  });
});
