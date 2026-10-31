// frontend/src/components/admin/summary-cards.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import type { AdminSummary } from "@/lib/admin-api";
import { formatNumber } from "@/lib/admin-format";
import { useTranslation } from "@/lib/i18n/provider";
import { interpolate } from "@/lib/i18n/interpolate";

function Card({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-xl border bg-card p-5 text-card-foreground">
      <h2 className="text-sm text-muted-foreground">{label}</h2>
      <p className="mt-1 text-3xl font-semibold">{value}</p>
      <p className="mt-2 text-sm text-muted-foreground">{hint}</p>
    </div>
  );
}

export function SummaryCards({ summary }: { summary: AdminSummary }) {
  const { t, locale } = useTranslation();
  const n = (value: number) => formatNumber(value, locale);
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Card
        label={t("admin.summary.accountsTotal")}
        value={n(summary.accountsTotal)}
        hint={interpolate(t("admin.summary.activeHint"), { count: n(summary.accountsActive30Days) })}
      />
      <Card
        label={t("admin.summary.publishers")}
        value={n(summary.accountsByRole.publisher)}
        hint={interpolate(t("admin.summary.publishersHint"), {
          publishers: n(summary.publishersWithAccounts), invitations: n(summary.openInvitations),
        })}
      />
      <Card
        label={t("admin.summary.administrators")}
        value={n(summary.accountsByRole.administrator)}
        hint={t("admin.summary.administratorsHint")}
      />
      <Card
        label={t("admin.summary.blocked")}
        value={n(summary.blocked)}
        hint={summary.mostFrequentBlockReason
          ? interpolate(t("admin.summary.blockedHint"), {
            reason: t(`admin.blockReasons.${summary.mostFrequentBlockReason}`),
          })
          : t("admin.summary.blockedNone")}
      />
    </div>
  );
}
