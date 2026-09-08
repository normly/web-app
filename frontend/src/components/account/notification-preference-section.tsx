// frontend/src/components/account/notification-preference-section.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { useTranslation } from "@/lib/i18n/provider";
import type { AccountSummary } from "@/lib/account-response";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

const OPTIONS: { value: string; labelKey: TranslationKey }[] = [
  { value: "none", labelKey: "account.notificationPreferenceNone" },
  { value: "in_app", labelKey: "account.notificationPreferenceInApp" },
  { value: "email", labelKey: "account.notificationPreferenceEmail" },
  { value: "both", labelKey: "account.notificationPreferenceBoth" },
];

export function NotificationPreferenceSection({
  account, onAccountUpdated,
}: {
  account: AccountSummary;
  onAccountUpdated: (account: AccountSummary) => void;
}) {
  const { t } = useTranslation();
  const [status, setStatus] = React.useState<"idle" | "error">("idle");

  const save = async (value: string) => {
    try {
      const response = await fetch("/api/account/profile", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ notification_preference: value }),
      });
      if (response.ok) {
        setStatus("idle");
        onAccountUpdated(await response.json());
      } else {
        setStatus("error");
      }
    } catch {
      setStatus("error");
    }
  };

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">{t("account.notificationPreferenceTitle")}</h2>
      <div className="flex flex-col gap-2">
        {OPTIONS.map((option) => (
          <label key={option.value} className="flex items-center gap-2 text-sm">
            <input
              type="radio" name="notification_preference" value={option.value}
              checked={account.notificationPreference === option.value}
              onChange={() => save(option.value)}
              aria-label={t(option.labelKey)}
            />
            {t(option.labelKey)}
          </label>
        ))}
      </div>
      {status === "error" && (
        <p className="text-sm text-destructive">{t("account.notificationPreferenceSaveError")}</p>
      )}
    </section>
  );
}
