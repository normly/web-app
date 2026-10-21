// frontend/src/lib/i18n/resolve-locale.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { NextRequest } from "next/server";
import type { Locale } from "@/lib/i18n/provider";

export const LOCALE_COOKIE = "normly_locale";

// One rule for the page and for every BFF route that triggers a mail: the
// language the visitor sees is the language their mail is written in.
export function resolveLocale(cookieValue: string | undefined, acceptLanguage: string | null): Locale {
  if (cookieValue === "de" || cookieValue === "en") {
    return cookieValue;
  }
  return (acceptLanguage ?? "").toLowerCase().startsWith("en") ? "en" : "de";
}

export function localeFromRequest(request: NextRequest): Locale {
  return resolveLocale(
    request.cookies.get(LOCALE_COOKIE)?.value,
    request.headers.get("accept-language"),
  );
}
