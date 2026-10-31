// frontend/src/components/admin/remove-dialog.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { adminApi, errorKey, type AdminUserRow } from "@/lib/admin-api";
import { useTranslation } from "@/lib/i18n/provider";
import { interpolate } from "@/lib/i18n/interpolate";

export function RemoveDialog({
  row, onClose, onDone,
}: { row: AdminUserRow; onClose: () => void; onDone: (text: string) => void }) {
  const { t } = useTranslation();
  const [typed, setTyped] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const matches = typed.trim().toLowerCase() === row.email.toLowerCase();

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const { emailSent } = await adminApi.remove(row.id, typed.trim());
      onDone(emailSent ? t("admin.notices.removed") : t("admin.notices.emailNotSent"));
    } catch (failure) {
      setError(t(errorKey(failure)));
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogTitle>{t("admin.remove.title")}</DialogTitle>
        <p className="text-sm text-muted-foreground">
          {interpolate(t("admin.remove.description"), { email: row.email })}
        </p>
        <label className="mt-4 flex flex-col gap-2 text-sm">
          {t("admin.remove.confirmLabel")}
          <Input value={typed} onChange={(event) => setTyped(event.target.value)} autoComplete="off" />
        </label>
        {error && <p role="alert" className="mt-2 text-sm text-destructive">{error}</p>}
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>{t("admin.remove.cancel")}</Button>
          <Button variant="destructive" disabled={!matches || busy} onClick={submit}>
            {t("admin.remove.confirm")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
