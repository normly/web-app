// frontend/src/components/jurisdiction-switcher.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { Landmark } from "lucide-react";
import { useJurisdiction, JURISDICTIONS, type Jurisdiction } from "@/lib/jurisdiction/provider";
import { useTranslation } from "@/lib/i18n/provider";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

export function JurisdictionSwitcher() {
  const { t } = useTranslation();
  const { jurisdiction, setJurisdiction } = useJurisdiction();
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex items-center gap-1.5 rounded-md border border-input bg-background px-2 h-9">
            <Landmark className="h-4 w-4 text-muted-foreground" />
            <select
              value={jurisdiction}
              onChange={(event) => setJurisdiction(event.target.value as Jurisdiction)}
              className="h-full bg-background text-sm outline-none"
              aria-label="Jurisdiktion"
            >
              {JURISDICTIONS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
        </TooltipTrigger>
        <TooltipContent>{t("nav.jurisdictionSwitcherTooltip")}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
