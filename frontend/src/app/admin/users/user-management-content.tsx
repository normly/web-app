// frontend/src/app/admin/users/user-management-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import Link from "next/link";
import { Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SummaryCards } from "@/components/admin/summary-cards";
import { UsersPagination } from "@/components/admin/users-pagination";
import { UsersTable } from "@/components/admin/users-table";
import { BlockDialog } from "@/components/admin/block-dialog";
import { InviteDialog } from "@/components/admin/invite-dialog";
import { EditDialog } from "@/components/admin/edit-dialog";
import { RemoveDialog } from "@/components/admin/remove-dialog";
import { RoleMatrixDialog } from "@/components/admin/role-matrix-dialog";
import { RowActions } from "@/components/admin/row-actions";
import { UsersToolbar } from "@/components/admin/users-toolbar";
import {
  AdminApiError, adminApi, errorKey, type AdminSummary, type AdminUserPage, type AdminUserRow, type SortKey,
} from "@/lib/admin-api";
import { useUsersQuery } from "@/lib/admin-users-query";
import { useTranslation } from "@/lib/i18n/provider";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";
import { useAccountSession } from "@/lib/use-account-session";

export type DialogState =
  | null
  | { kind: "edit" | "block" | "remove"; row: AdminUserRow }
  | { kind: "invite" }
  | { kind: "matrix" };

export type Notice = { kind: "success" | "error"; text: string } | null;

export function UserManagementContent() {
  const { t } = useTranslation();
  const { account } = useAccountSession();
  const { query, update } = useUsersQuery();
  const [page, setPage] = React.useState<AdminUserPage | null>(null);
  const [summary, setSummary] = React.useState<AdminSummary | null>(null);
  const [state, setState] = React.useState<"loading" | "ready" | "forbidden" | "signedOut" | "error">("loading");
  // A refetch that fails after the page was ready keeps the table and shows a notice.
  const [refetchFailed, setRefetchFailed] = React.useState(false);
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
        setRefetchFailed(false);
      })
      .catch((error) => {
        if (cancelled) return;
        const status = error instanceof AdminApiError ? error.status : null;
        if (status === 401) setState("signedOut");
        else if (status === 403) setState("forbidden");
        else {
          setState((current) => (current === "ready" ? "ready" : "error"));
          setRefetchFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [query, reloadKey]);

  // After a reload the current page may no longer exist (e.g. the last row on
  // the last page was removed): go to the last page that does.
  const lastPage = page ? Math.max(1, Math.ceil(page.total / query.pageSize)) : null;
  React.useEffect(() => {
    if (lastPage !== null && query.page > lastPage) update({ page: lastPage });
  }, [lastPage, query.page, update]);

  const done = (text: string) => {
    setDialog(null);
    setNotice({ kind: "success", text });
    reload();
  };
  async function quick(action: () => Promise<{ emailSent: boolean } | void>, key: TranslationKey) {
    try {
      const result = await action();
      done(result && result.emailSent === false ? t("admin.notices.emailNotSent") : t(key));
    } catch (failure) {
      setNotice({ kind: "error", text: t(errorKey(failure)) });
    }
  }

  const onSort = (sort: SortKey) =>
    update({ sort, order: query.sort === sort && query.order === "asc" ? "desc" : "asc" });

  if (state === "signedOut") {
    return (
      <p className="text-sm">
        {t("admin.sessionExpired")}{" "}
        <Link href="/login" className="underline">{t("admin.signInAgain")}</Link>
      </p>
    );
  }
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
      {refetchFailed && (
        <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-destructive">
          <span>{t("admin.loadError")}</span>
          <Button variant="outline" size="sm" onClick={reload}>{t("admin.retry")}</Button>
        </div>
      )}
      {summary && <SummaryCards summary={summary} />}
      <UsersToolbar query={query} summary={summary} onChange={update} />
      {page && (
        <>
          <UsersTable
            rows={page.rows}
            query={query}
            onSort={onSort}
            renderActions={(row) => (
              <RowActions
                row={row}
                isSelf={row.kind === "account" && row.id === account?.accountId}
                onOpen={(kind) => setDialog({ kind, row })}
                onResend={() => quick(() => adminApi.resendInvitation(row.id), "admin.notices.resent")}
                onWithdraw={() => quick(() => adminApi.withdrawInvitation(row.id), "admin.notices.withdrawn")}
                onUnblock={() => quick(() => adminApi.unblock(row.id), "admin.notices.unblocked")}
              />
            )}
          />
          <UsersPagination query={query} total={page.total} onChange={update} />
        </>
      )}
      {dialog?.kind === "invite" && <InviteDialog onClose={() => setDialog(null)} onDone={done} />}
      {dialog?.kind === "edit" && <EditDialog row={dialog.row} onClose={() => setDialog(null)} onDone={done} />}
      {dialog?.kind === "block" && <BlockDialog row={dialog.row} onClose={() => setDialog(null)} onDone={done} />}
      {dialog?.kind === "remove" && <RemoveDialog row={dialog.row} onClose={() => setDialog(null)} onDone={done} />}
      {dialog?.kind === "matrix" && <RoleMatrixDialog onClose={() => setDialog(null)} />}
      <div>
        <Button variant="outline" size="sm" onClick={() => setDialog({ kind: "matrix" })}>
          <Info />
          {t("admin.roleMatrix.button")}
        </Button>
      </div>
    </div>
  );
}
