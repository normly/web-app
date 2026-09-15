// frontend/src/components/locale-switcher.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { Languages } from "lucide-react";
import { useTranslation } from "@/lib/i18n/provider";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

export function LocaleSwitcher() {
  const { t, locale, setLocale } = useTranslation();
  const other = locale === "de" ? "en" : "de";
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="ghost" size="sm" className="gap-1.5" onClick={() => setLocale(other)}>
            <Languages className="h-4 w-4" />
            {other.toUpperCase()}
          </Button>
        </TooltipTrigger>
        <TooltipContent>{t("nav.languageSwitcherTooltip")}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
