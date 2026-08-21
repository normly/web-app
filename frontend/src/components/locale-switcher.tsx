// frontend/src/components/locale-switcher.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { useTranslation } from "@/lib/i18n/provider";
import { Button } from "@/components/ui/button";

export function LocaleSwitcher() {
  const { locale, setLocale } = useTranslation();
  const other = locale === "de" ? "en" : "de";
  return (
    <Button variant="ghost" size="sm" onClick={() => setLocale(other)}>
      {other.toUpperCase()}
    </Button>
  );
}
