// frontend/src/components/admin/block-dialog.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { NativeSelect } from "@/components/ui/native-select";
import { BLOCK_REASONS, adminApi, errorKey, type AdminUserRow, type BlockReason } from "@/lib/admin-api";
import { useTranslation } from "@/lib/i18n/provider";
import { interpolate } from "@/lib/i18n/interpolate";

export function BlockDialog({
  row, onClose, onDone,
}: { row: AdminUserRow; onClose: () => void; onDone: (text: string) => void }) {
  const { t } = useTranslation();
  const [reason, setReason] = React.useState<BlockReason>("bulk_retrieval");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const { emailSent } = await adminApi.block(row.id, reason);
      onDone(emailSent ? t("admin.notices.blocked") : t("admin.notices.emailNotSent"));
    } catch (failure) {
      setError(t(errorKey(failure)));
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogTitle>{t("admin.block.title")}</DialogTitle>
        <p className="text-sm text-muted-foreground">
          {interpolate(t("admin.block.description"), { email: row.email })}
        </p>
        <label className="mt-4 flex flex-col gap-2 text-sm">
          {t("admin.block.reason")}
          <NativeSelect value={reason} onChange={(event) => setReason(event.target.value as BlockReason)}>
            {BLOCK_REASONS.map((r) => (
              <option key={r} value={r}>{t(`admin.blockReasons.${r}`)}</option>
            ))}
          </NativeSelect>
        </label>
        {error && <p role="alert" className="mt-2 text-sm text-destructive">{error}</p>}
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>{t("admin.block.cancel")}</Button>
          <Button variant="destructive" disabled={busy} onClick={submit}>
            {t("admin.block.confirm")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
