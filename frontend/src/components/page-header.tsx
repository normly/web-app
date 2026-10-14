// frontend/src/components/page-header.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Bell, FileDiff, FileX, Globe, Scale } from "lucide-react";
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
  no_longer_available: "nav.notificationNoLongerAvailable",
};

const TRIGGER_TYPE_ICONS: Record<string, typeof FileDiff> = {
  new_edition: FileDiff,
  national_adoption: Globe,
  rights_change: Scale,
  no_longer_available: FileX,
};

function TriggerTypeIcon({ triggerType, className }: { triggerType: string; className?: string }) {
  const Icon = TRIGGER_TYPE_ICONS[triggerType] ?? Bell;
  return <Icon className={className} />;
}

export function PageHeader({
  titleKey,
  subtitleKey,
}: {
  titleKey: TranslationKey;
  subtitleKey?: TranslationKey;
}) {
  const { t, locale } = useTranslation();
  const { notifications, unreadCount, markRead } = useNotifications();

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
            <Button
              variant="outline"
              size="icon"
              className="relative"
              aria-label={t("nav.notificationsLabel")}
            >
              <Bell className="h-4 w-4" />
              {unreadCount > 0 && (
                <span
                  data-testid="unread-badge"
                  className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] font-medium text-destructive-foreground"
                >
                  <span className="sr-only">
                    {`${unreadCount} ${t("nav.unreadNotificationsCountSuffix")}`}
                  </span>
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end">
            {notifications.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("nav.noNotifications")}</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {notifications.map((notification) => (
                  <li key={notification.id}>
                    <button
                      type="button"
                      data-testid={`notification-${notification.id}`}
                      onClick={() => markRead(notification.id)}
                      className="flex w-full items-start gap-2 rounded-md p-2 text-left text-sm hover:bg-muted"
                    >
                      {notification.readAt === null ? (
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary">
                          <span className="sr-only">{t("nav.notificationItemUnreadBadge")}</span>
                        </span>
                      ) : (
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0" />
                      )}
                      <TriggerTypeIcon
                        triggerType={notification.triggerType}
                        className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
                      />
                      <span className="flex flex-col">
                        <span>{t(TRIGGER_TYPE_KEYS[notification.triggerType] ?? "nav.notificationsLabel")}</span>
                        <span className="text-xs text-muted-foreground">
                          {new Date(notification.createdAt).toLocaleDateString(locale)}
                        </span>
                      </span>
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
