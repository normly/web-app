// frontend/src/lib/i18n/provider.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import de from "./de.json";
import en from "./en.json";
import type { TranslationKey } from "./dictionary-keys";

const DICTIONARIES = { de, en } as const;
export type Locale = keyof typeof DICTIONARIES;

interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: TranslationKey) => string;
}

const LocaleContext = React.createContext<LocaleContextValue | null>(null);

function lookup(dictionary: object, key: string): string {
  const value = key.split(".").reduce<unknown>((node, part) => {
    if (node && typeof node === "object" && part in node) {
      return (node as Record<string, unknown>)[part];
    }
    return undefined;
  }, dictionary);
  // A key present in the TranslationKey type is always present in both
  // dictionaries (Step 3's test pins this) -- reaching `undefined` here
  // would mean the dictionaries drifted out of sync at runtime, not a
  // normal user-facing condition, so falling back to the raw key (rather
  // than throwing) keeps the UI readable while surfacing the bug visibly.
  return typeof value === "string" ? value : key;
}

export function LocaleProvider({
  children,
  initialLocale,
}: {
  children: React.ReactNode;
  initialLocale: Locale;
}) {
  const [locale, setLocaleState] = React.useState<Locale>(initialLocale);

  const setLocale = React.useCallback((next: Locale) => {
    setLocaleState(next);
    document.cookie = `normly_locale=${next}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`;
  }, []);

  const t = React.useCallback(
    (key: TranslationKey) => lookup(DICTIONARIES[locale], key),
    [locale],
  );

  const value = React.useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useTranslation(): LocaleContextValue {
  const context = React.useContext(LocaleContext);
  if (context === null) {
    throw new Error("useTranslation must be used within a LocaleProvider");
  }
  return context;
}
