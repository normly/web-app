// frontend/src/components/account/email-section.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";
import type { AccountSummary } from "@/lib/account-response";

export function EmailSection({ account }: { account: AccountSummary }) {
  const { t } = useTranslation();
  const [newEmail, setNewEmail] = React.useState("");
  const [status, setStatus] = React.useState<"idle" | "sent" | "error">("idle");
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const response = await fetch("/api/account/email", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ new_email: newEmail }),
      });
      setStatus(response.ok ? "sent" : "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{t("account.emailTitle")}</h2>
      <p className="text-sm text-muted-foreground">
        {t("account.currentEmailLabel")}: <span>{account.email}</span>
      </p>
      {status === "sent" ? (
        <p className="text-sm">{t("account.emailChangeSentMessage")}</p>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            {t("account.newEmailLabel")}
            <Input
              type="email" value={newEmail} onChange={(event) => setNewEmail(event.target.value)}
              required
            />
          </label>
          {status === "error" && (
            <p className="text-sm text-red-600">{t("account.emailChangeGenericError")}</p>
          )}
          <Button type="submit" disabled={isSubmitting} className="self-start">
            {t("account.requestEmailChangeButton")}
          </Button>
        </form>
      )}
    </section>
  );
}
