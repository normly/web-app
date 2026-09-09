// frontend/src/components/account/notification-preference-section.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Switch } from "@/components/ui/switch";
import { useTranslation } from "@/lib/i18n/provider";
import type { AccountSummary } from "@/lib/account-response";

function computePreference(isInApp: boolean, isEmail: boolean): string {
  if (isInApp && isEmail) return "both";
  if (isInApp) return "in_app";
  if (isEmail) return "email";
  return "none";
}

export function NotificationPreferenceSection({
  account, onAccountUpdated,
}: {
  account: AccountSummary;
  onAccountUpdated: (account: AccountSummary) => void;
}) {
  const { t } = useTranslation();
  const [status, setStatus] = React.useState<"idle" | "error">("idle");
  const [isSaving, setIsSaving] = React.useState(false);

  const isInApp = account.notificationPreference === "in_app" || account.notificationPreference === "both";
  const isEmail = account.notificationPreference === "email" || account.notificationPreference === "both";

  const save = async (nextIsInApp: boolean, nextIsEmail: boolean) => {
    setIsSaving(true);
    try {
      const response = await fetch("/api/account/profile", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ notification_preference: computePreference(nextIsInApp, nextIsEmail) }),
      });
      if (response.ok) {
        setStatus("idle");
        onAccountUpdated(await response.json());
      } else {
        setStatus("error");
      }
    } catch {
      setStatus("error");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">{t("account.notificationPreferenceTitle")}</h2>
      <div className="divide-y">
        <div className="flex items-center justify-between gap-4 py-3">
          <div className="space-y-0.5">
            <p className="text-sm font-medium">{t("account.notificationChannelInAppTitle")}</p>
            <p className="text-sm text-muted-foreground">{t("account.notificationChannelInAppDescription")}</p>
          </div>
          <Switch
            aria-label={t("account.notificationChannelInAppTitle")}
            checked={isInApp}
            disabled={isSaving}
            onCheckedChange={(checked) => save(checked, isEmail)}
          />
        </div>
        <div className="flex items-center justify-between gap-4 py-3">
          <div className="space-y-0.5">
            <p className="text-sm font-medium">{t("account.notificationChannelEmailTitle")}</p>
            <p className="text-sm text-muted-foreground">{t("account.notificationChannelEmailDescription")}</p>
          </div>
          <Switch
            aria-label={t("account.notificationChannelEmailTitle")}
            checked={isEmail}
            disabled={isSaving}
            onCheckedChange={(checked) => save(isInApp, checked)}
          />
        </div>
      </div>
      {status === "error" && (
        <p className="text-sm text-destructive">{t("account.notificationPreferenceSaveError")}</p>
      )}
    </section>
  );
}
