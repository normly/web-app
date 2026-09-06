// frontend/src/components/account/delete-account-section.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";
import type { AccountSummary } from "@/lib/account-response";

// The typed-email confirmation is a frontend-only speed bump against
// misclicks -- it is never sent to the backend. The backend's own
// authority for this destructive action is the DeleteAccountRequest.password
// field (Task 8), required whenever the account has a password hash at all;
// a passwordless account relies solely on its valid session, same as Task 8's
// delete_account handler already documents.
export function DeleteAccountSection({ account }: { account: AccountSummary }) {
  const { t } = useTranslation();
  const [confirmEmail, setConfirmEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const canDelete =
    confirmEmail === account.email && (!account.hasPassword || password.trim().length > 0);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const response = await fetch("/api/account/delete", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ password: password || null }),
      });
      if (response.ok) {
        window.location.reload();
      } else {
        setError(true);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="flex flex-col gap-3 rounded border border-destructive p-4">
      <h2 className="text-lg font-semibold text-destructive">{t("account.deleteAccountTitle")}</h2>
      <p className="text-sm text-muted-foreground">{t("account.deleteAccountDescription")}</p>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          {t("account.deleteAccountConfirmLabel")}
          <Input value={confirmEmail} onChange={(event) => setConfirmEmail(event.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("account.deleteAccountPasswordLabel")}
          <Input
            type="password" value={password} onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error && <p className="text-sm text-destructive">{t("account.deleteAccountError")}</p>}
        <Button
          type="submit" disabled={!canDelete || isSubmitting}
          variant="destructive" className="self-start"
        >
          {t("account.deleteAccountButton")}
        </Button>
      </form>
    </section>
  );
}
