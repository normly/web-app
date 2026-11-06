// frontend/src/components/admin/users-pagination.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { PAGE_SIZES, type UsersQuery } from "@/lib/admin-api";
import { formatNumber } from "@/lib/admin-format";
import { useTranslation } from "@/lib/i18n/provider";
import { interpolate } from "@/lib/i18n/interpolate";

export function UsersPagination({
  query, total, onChange,
}: {
  query: UsersQuery;
  total: number;
  onChange: (patch: Partial<UsersQuery>) => void;
}) {
  const { t, locale } = useTranslation();
  const pages = Math.max(1, Math.ceil(total / query.pageSize));
  const from = total === 0 ? 0 : (query.page - 1) * query.pageSize + 1;
  const to = Math.min(query.page * query.pageSize, total);
  const n = (value: number) => formatNumber(value, locale);
  const go = (page: number) => onChange({ page });

  return (
    <div className="flex flex-col gap-3 text-sm sm:flex-row sm:items-center sm:justify-between">
      <p className="text-muted-foreground">
        {interpolate(t("admin.pagination.showing"), { from: n(from), to: n(to), total: n(total) })}
      </p>
      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2">
          <span>{t("admin.pagination.rowsPerPage")}</span>
          <NativeSelect
            className="h-9 w-auto"
            value={query.pageSize}
            onChange={(event) => onChange({ pageSize: Number(event.target.value) })}
          >
            {PAGE_SIZES.map((size) => <option key={size} value={size}>{size}</option>)}
          </NativeSelect>
        </label>
        <span>{interpolate(t("admin.pagination.page"), { page: n(query.page), pages: n(pages) })}</span>
        <div className="flex gap-1">
          <Button variant="outline" size="icon" aria-label={t("admin.pagination.first")}
                  disabled={query.page <= 1} onClick={() => go(1)}>
            <ChevronsLeft />
          </Button>
          <Button variant="outline" size="icon" aria-label={t("admin.pagination.previous")}
                  disabled={query.page <= 1} onClick={() => go(query.page - 1)}>
            <ChevronLeft />
          </Button>
          <Button variant="outline" size="icon" aria-label={t("admin.pagination.next")}
                  disabled={query.page >= pages} onClick={() => go(query.page + 1)}>
            <ChevronRight />
          </Button>
          <Button variant="outline" size="icon" aria-label={t("admin.pagination.last")}
                  disabled={query.page >= pages} onClick={() => go(pages)}>
            <ChevronsRight />
          </Button>
        </div>
      </div>
    </div>
  );
}
