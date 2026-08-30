// frontend/src/components/account/password-section.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

export function PasswordSection() {
  const { t } = useTranslation();
  const [currentPassword, setCurrentPassword] = React.useState("");
  const [newPassword, setNewPassword] = React.useState("");
  const [status, setStatus] = React.useState<"idle" | "success" | "error">("idle");
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const response = await fetch("/api/account/password", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          current_password: currentPassword || null, new_password: newPassword,
        }),
      });
      setStatus(response.ok ? "success" : "error");
      if (response.ok) {
        setCurrentPassword("");
        setNewPassword("");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{t("account.passwordTitle")}</h2>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          {t("account.currentPasswordLabel")}
          <Input
            type="password" value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("account.newPasswordLabel")}
          <Input
            type="password" value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)} required
          />
        </label>
        {status === "success" && (
          <p className="text-sm">{t("account.passwordChangedMessage")}</p>
        )}
        {status === "error" && (
          <p className="text-sm text-red-600">{t("account.passwordChangeError")}</p>
        )}
        <Button type="submit" disabled={isSubmitting} className="self-start">
          {t("account.changePasswordButton")}
        </Button>
      </form>
    </section>
  );
}
