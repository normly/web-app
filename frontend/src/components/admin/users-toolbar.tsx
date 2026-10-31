// frontend/src/components/admin/users-toolbar.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { AdminSummary, UsersQuery } from "@/lib/admin-api";
import { formatNumber } from "@/lib/admin-format";
import { useTranslation } from "@/lib/i18n/provider";

const TABS = ["all", "user", "administrator", "publisher"] as const;
const STATUS_OPTIONS = ["all", "active", "invited", "expired", "blocked"] as const;

export function UsersToolbar({
  query, summary, onChange,
}: {
  query: UsersQuery;
  summary: AdminSummary | null;
  onChange: (patch: Partial<UsersQuery>) => void;
}) {
  const { t, locale } = useTranslation();
  const [text, setText] = React.useState(query.q);
  const lastSent = React.useRef(query.q);

  // The URL is the source of truth: an external change of q (navigation) wins.
  React.useEffect(() => {
    if (query.q !== lastSent.current) {
      lastSent.current = query.q;
      setText(query.q);
    }
  }, [query.q]);

  // 300 ms debounce; the URL stays the single source of truth.
  React.useEffect(() => {
    if (text === query.q) return;
    const timer = window.setTimeout(() => {
      lastSent.current = text;
      onChange({ q: text });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [text, query.q, onChange]);

  const count = (tab: (typeof TABS)[number]) => {
    if (!summary) return null;
    return formatNumber(tab === "all" ? summary.accountsTotal : summary.accountsByRole[tab], locale);
  };

  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex flex-wrap items-center gap-3">
        <div className="max-w-full overflow-x-auto">
        <Tabs value={query.role} onValueChange={(value) => onChange({ role: value as UsersQuery["role"] })}>
          <TabsList>
            {TABS.map((tab) => (
              <TabsTrigger key={tab} value={tab} className="gap-2">
                {t(`admin.tabs.${tab}`)}
                {count(tab) !== null && (
                  <span className="rounded bg-muted px-1.5 text-xs text-muted-foreground">{count(tab)}</span>
                )}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <span>{t("admin.status.label")}</span>
          <NativeSelect
            className="h-9 w-auto"
            value={query.status}
            onChange={(event) => onChange({ status: event.target.value as UsersQuery["status"] })}
          >
            {STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>{t(`admin.status.${status}`)}</option>
            ))}
          </NativeSelect>
        </label>
      </div>
      <Input
        type="search"
        maxLength={200}
        aria-label={t("admin.searchLabel")}
        placeholder={t("admin.searchPlaceholder")}
        className="lg:max-w-xs"
        value={text}
        onChange={(event) => setText(event.target.value)}
      />
    </div>
  );
}
