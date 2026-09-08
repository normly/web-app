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
import { useNotifications } from "@/lib/use-notifications";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

const TRIGGER_TYPE_KEYS: Record<string, TranslationKey> = {
  new_edition: "edgeType.replaces",
  national_adoption: "edgeType.adopted_from",
  rights_change: "documentDetail.rightsHeading",
};

export function PageHeader({
  titleKey,
  subtitleKey,
}: {
  titleKey: TranslationKey;
  subtitleKey?: TranslationKey;
}) {
  const { t } = useTranslation();
  const { notifications, markRead } = useNotifications();

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
            {notifications.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("nav.noNotifications")}</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {notifications.map((notification) => (
                  <li key={notification.id}>
                    <button
                      type="button"
                      data-testid={`notification-${notification.id}`}
                      onClick={() => markRead(notification.id)}
                      className="flex w-full items-center justify-between gap-2 rounded-md p-2 text-left text-sm hover:bg-muted"
                    >
                      <span>{t(TRIGGER_TYPE_KEYS[notification.triggerType] ?? "nav.notificationsLabel")}</span>
                      {notification.readAt === null && (
                        <span className="text-xs text-primary">{t("nav.notificationItemUnreadBadge")}</span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </PopoverContent>
        </Popover>
      </div>
    </header>
  );
}
