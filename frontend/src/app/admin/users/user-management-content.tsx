// frontend/src/app/admin/users/user-management-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SummaryCards } from "@/components/admin/summary-cards";
import { UsersPagination } from "@/components/admin/users-pagination";
import { UsersTable } from "@/components/admin/users-table";
import { UsersToolbar } from "@/components/admin/users-toolbar";
import {
  AdminApiError, adminApi, type AdminSummary, type AdminUserPage, type AdminUserRow, type SortKey,
} from "@/lib/admin-api";
import { useUsersQuery } from "@/lib/admin-users-query";
import { useTranslation } from "@/lib/i18n/provider";

export type DialogState =
  | null
  | { kind: "edit" | "block" | "remove"; row: AdminUserRow }
  | { kind: "invite" }
  | { kind: "matrix" };

export type Notice = { kind: "success" | "error"; text: string } | null;

export function UserManagementContent() {
  const { t } = useTranslation();
  const { query, update } = useUsersQuery();
  const [page, setPage] = React.useState<AdminUserPage | null>(null);
  const [summary, setSummary] = React.useState<AdminSummary | null>(null);
  const [state, setState] = React.useState<"loading" | "ready" | "forbidden" | "error">("loading");
  const [reloadKey, setReloadKey] = React.useState(0);
  const [dialog, setDialog] = React.useState<DialogState>(null);
  const [notice, setNotice] = React.useState<Notice>(null);
  const reload = React.useCallback(() => setReloadKey((k) => k + 1), []);

  React.useEffect(() => {
    let cancelled = false;
    Promise.all([adminApi.listUsers(query), adminApi.summary()])
      .then(([users, totals]) => {
        if (cancelled) return;
        setPage(users);
        setSummary(totals);
        setState("ready");
      })
      .catch((error) => {
        if (cancelled) return;
        setState(error instanceof AdminApiError && (error.status === 403 || error.status === 401)
          ? "forbidden" : "error");
      });
    return () => {
      cancelled = true;
    };
  }, [query, reloadKey]);

  const onSort = (sort: SortKey) =>
    update({ sort, order: query.sort === sort && query.order === "asc" ? "desc" : "asc" });

  if (state === "forbidden") return <p className="text-sm">{t("admin.noAccess")}</p>;
  if (state === "error") return <p role="alert" className="text-sm text-destructive">{t("admin.loadError")}</p>;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-end">
        <Button onClick={() => setDialog({ kind: "invite" })}>{t("admin.inviteButton")}</Button>
      </div>
      {notice && (
        <p role={notice.kind === "error" ? "alert" : "status"}
           className={notice.kind === "error" ? "text-sm text-destructive" : "text-sm"}>
          {notice.text}
        </p>
      )}
      {summary && <SummaryCards summary={summary} />}
      <UsersToolbar query={query} summary={summary} onChange={update} />
      {page && (
        <>
          <UsersTable
            rows={page.rows}
            query={query}
            onSort={onSort}
            renderActions={() => null /* Task 7 */}
          />
          <UsersPagination query={query} total={page.total} onChange={update} />
        </>
      )}
      <div>
        <Button variant="outline" size="sm" onClick={() => setDialog({ kind: "matrix" })}>
          <Info />
          {t("admin.roleMatrix.button")}
        </Button>
      </div>
    </div>
  );
}
