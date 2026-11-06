// frontend/src/components/admin/users-table.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { RoleBadge, StatusBadge } from "@/components/admin/badges";
import type { AdminUserRow, SortKey, UsersQuery } from "@/lib/admin-api";
import { formatDate, formatLastLogin } from "@/lib/admin-format";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";
import { useTranslation } from "@/lib/i18n/provider";

type Translate = (key: TranslationKey) => string;
type Locale = "de" | "en";

interface Column {
  sort: SortKey;
  label: TranslationKey;
  cell: (row: AdminUserRow, t: Translate, locale: Locale) => React.ReactNode;
}

const dash = <span className="text-muted-foreground">–</span>;

// One definition per column: header, sort key and cell. All left-aligned.
const COLUMNS: Column[] = [
  { sort: "email", label: "admin.columns.account", cell: (r) => <span className="font-medium">{r.email}</span> },
  { sort: "first_name", label: "admin.columns.firstName", cell: (r) => r.firstName ?? dash },
  { sort: "last_name", label: "admin.columns.lastName", cell: (r) => r.lastName ?? dash },
  {
    sort: "sign_in", label: "admin.columns.signIn",
    cell: (r, t) => r.signInMethods.length
      ? r.signInMethods.map((m) => t(`admin.signIn.${m}` as TranslationKey)).join(", ")
      : dash,
  },
  { sort: "role", label: "admin.columns.role", cell: (r) => <RoleBadge role={r.role} /> },
  { sort: "publisher", label: "admin.columns.publisher", cell: (r) => r.publisherName ?? dash },
  {
    sort: "last_login_at", label: "admin.columns.lastLogin",
    cell: (r, t, locale) => r.kind === "invitation"
      ? t("admin.never")
      : formatLastLogin(r.lastLoginAt, locale, t),
  },
  {
    sort: "created_at", label: "admin.columns.createdAt",
    cell: (r, _t, locale) => (r.createdAt ? formatDate(r.createdAt, locale) : dash),
  },
  { sort: "status", label: "admin.columns.status", cell: (r) => <StatusBadge status={r.status} /> },
];

export function UsersTable({
  rows, query, onSort, renderActions,
}: {
  rows: AdminUserRow[];
  query: UsersQuery;
  onSort: (sort: SortKey) => void;
  renderActions: (row: AdminUserRow) => React.ReactNode;
}) {
  const { t, locale } = useTranslation();
  return (
    <div className="overflow-x-auto rounded-xl border">
      <Table>
        <TableHeader>
          <TableRow>
            {COLUMNS.map((column) => {
              const active = query.sort === column.sort;
              const Icon = !active ? ArrowUpDown : query.order === "asc" ? ArrowUp : ArrowDown;
              return (
                <TableHead
                  key={column.sort}
                  className="text-left"
                  aria-sort={active ? (query.order === "asc" ? "ascending" : "descending") : "none"}
                >
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 font-medium text-foreground"
                    onClick={() => onSort(column.sort)}
                  >
                    {t(column.label)}
                    <Icon className="size-3 text-muted-foreground" aria-hidden />
                  </button>
                </TableHead>
              );
            })}
            <TableHead className="text-left">
              <span className="sr-only">{t("admin.columns.actions")}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={COLUMNS.length + 1} className="text-left text-muted-foreground">
                {t("admin.empty")}
              </TableCell>
            </TableRow>
          ) : rows.map((row) => (
            <TableRow key={`${row.kind}-${row.id}`}>
              {COLUMNS.map((column) => (
                <TableCell key={column.sort} className="whitespace-nowrap text-left">
                  {column.cell(row, t, locale)}
                </TableCell>
              ))}
              <TableCell className="text-left">{renderActions(row)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
