// frontend/src/components/page-header.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { JurisdictionSwitcher } from "@/components/jurisdiction-switcher";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { ModeToggle } from "@/components/mode-toggle";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useTranslation } from "@/lib/i18n/provider";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

export function PageHeader({
  titleKey,
  subtitleKey,
}: {
  titleKey: TranslationKey;
  subtitleKey?: TranslationKey;
}) {
  const { t } = useTranslation();

  return (
    <header className="flex items-center justify-between gap-4 border-b p-4">
      <div className="flex items-center gap-2">
        <SidebarTrigger aria-label={t("nav.toggleSidebar")} />
        <div>
          <h1 className="text-lg font-semibold">{t(titleKey)}</h1>
          {subtitleKey && <p className="text-sm text-muted-foreground">{t(subtitleKey)}</p>}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <LocaleSwitcher />
        <JurisdictionSwitcher />
        <ModeToggle />
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" size="icon" aria-label={t("nav.notificationsLabel")}>
              <Bell className="h-4 w-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end">
            <p className="text-sm text-muted-foreground">{t("nav.noNotifications")}</p>
          </PopoverContent>
        </Popover>
      </div>
    </header>
  );
}
