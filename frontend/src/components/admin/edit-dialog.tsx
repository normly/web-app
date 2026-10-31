// frontend/src/components/admin/edit-dialog.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { NativeSelect } from "@/components/ui/native-select";
import { RoleBadge } from "@/components/admin/badges";
import { adminApi, errorKey, type AdminUserRow, type Publisher } from "@/lib/admin-api";
import { useTranslation } from "@/lib/i18n/provider";

// Fewer rights at once, more rights only by invitation (ADR-030): a publisher
// can change its binding, publishers and administrators can be downgraded.
export function EditDialog({
  row, onClose, onDone,
}: { row: AdminUserRow; onClose: () => void; onDone: (text: string) => void }) {
  const { t } = useTranslation();
  const [publishers, setPublishers] = React.useState<Publisher[]>([]);
  const [publisherId, setPublisherId] = React.useState(row.publisherId ?? "");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (row.role !== "publisher") return;
    adminApi.publishers().then(setPublishers).catch(() => setPublishers([]));
  }, [row.role]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onDone(t("admin.notices.saved"));
    } catch (failure) {
      setError(t(errorKey(failure)));
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogTitle>{t("admin.edit.title")}</DialogTitle>
        <p className="text-sm">{row.email}</p>
        <div className="mt-2"><RoleBadge role={row.role} /></div>
        {row.role === "publisher" && (
          <label className="mt-4 flex flex-col gap-2 text-sm">
            {t("admin.edit.publisher")}
            <NativeSelect value={publisherId} onChange={(event) => setPublisherId(event.target.value)}>
              {publishers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </NativeSelect>
          </label>
        )}
        <p className="mt-4 text-sm text-muted-foreground">{t("admin.edit.upgradeHint")}</p>
        {error && <p role="alert" className="mt-2 text-sm text-destructive">{error}</p>}
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <Button variant="outline" onClick={onClose}>{t("admin.edit.cancel")}</Button>
          {row.role !== "user" && (
            <Button variant="outline" disabled={busy}
                    onClick={() => run(() => adminApi.downgradeToUser(row.id))}>
              {t("admin.edit.downgrade")}
            </Button>
          )}
          {row.role === "publisher" && (
            <Button disabled={busy || !publisherId || publisherId === row.publisherId}
                    onClick={() => run(() => adminApi.changePublisher(row.id, publisherId))}>
              {t("admin.edit.save")}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
