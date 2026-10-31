// frontend/src/lib/admin-format.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { TranslationKey } from "@/lib/i18n/dictionary-keys";
import { interpolate } from "@/lib/i18n/interpolate";

type Locale = "de" | "en";
const TAG: Record<Locale, string> = { de: "de-DE", en: "en-GB" };

export function formatNumber(value: number, locale: Locale): string {
  return new Intl.NumberFormat(TAG[locale]).format(value);
}

export function formatDate(iso: string, locale: Locale): string {
  return new Intl.DateTimeFormat(TAG[locale], { day: "2-digit", month: "2-digit", year: "numeric" })
    .format(new Date(iso));
}

function formatTime(date: Date, locale: Locale): string {
  return new Intl.DateTimeFormat(TAG[locale], { hour: "2-digit", minute: "2-digit" }).format(date);
}

export function formatDateTime(iso: string, locale: Locale): string {
  const date = new Date(iso);
  return `${formatDate(iso, locale)} ${formatTime(date, locale)}`;
}

function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth()
    && a.getDate() === b.getDate();
}

export function formatLastLogin(
  iso: string | null, locale: Locale, t: (key: TranslationKey) => string, now: Date = new Date(),
): string {
  if (!iso) return t("admin.never");
  const date = new Date(iso);
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay(date, now)) return interpolate(t("admin.today"), { time: formatTime(date, locale) });
  if (sameDay(date, yesterday)) {
    return interpolate(t("admin.yesterday"), { time: formatTime(date, locale) });
  }
  return formatDateTime(iso, locale);
}
