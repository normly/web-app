// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { interpolate } from "@/lib/i18n/interpolate";
import { useTranslation } from "@/lib/i18n/provider";
import { formatRelativeReset, formatResetTime } from "@/lib/reset-time";

interface RawUsage {
  used: number;
  limit: number;
  resets_at: string;
  pool_exhausted: boolean;
  pool_resets_at: string | null;
}

export function UsageSection() {
  const { t, locale } = useTranslation();
  const [usage, setUsage] = React.useState<RawUsage | null>(null);
  const [status, setStatus] = React.useState<"loading" | "ready" | "error">("loading");

  React.useEffect(() => {
    fetch("/api/account/usage")
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error("load failed"))))
      .then((body: RawUsage) => {
        setUsage(body);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{t("account.usageTitle")}</h2>
      <p className="text-sm text-muted-foreground">{t("account.usageDescription")}</p>
      {status === "loading" && <Skeleton className="h-20 w-full" />}
      {status === "error" && <p className="text-sm text-destructive">{t("account.usageLoadError")}</p>}
      {status === "ready" && usage && (
        <div className="flex flex-col gap-2 rounded-lg border p-4">
          <p className="text-sm font-medium">
            {interpolate(t("account.usageAiAnswersToday"), {
              used: String(usage.used), limit: String(usage.limit),
            })}
          </p>
          <Progress
            value={usage.limit > 0 ? Math.min(100, (usage.used / usage.limit) * 100) : 100}
            aria-label={t("account.usageTitle")}
          />
          <p className="text-xs text-muted-foreground">
            {interpolate(t("account.usageResetsAt"), {
              time: formatResetTime(usage.resets_at, locale),
              relative: formatRelativeReset(usage.resets_at, locale),
            })}
          </p>
        </div>
      )}
      {status === "ready" && usage?.pool_exhausted && usage.pool_resets_at && (
        <p role="status" className="rounded-md border bg-muted p-3 text-sm">
          {interpolate(t("chat.poolExhausted"), {
            time: formatResetTime(usage.pool_resets_at, locale),
          })}
        </p>
      )}
    </section>
  );
}
