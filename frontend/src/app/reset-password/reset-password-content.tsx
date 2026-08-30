// frontend/src/app/reset-password/reset-password-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

function ResetPasswordForm() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [newPassword, setNewPassword] = React.useState("");
  const [status, setStatus] = React.useState<"idle" | "success" | "error">("idle");
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const response = await fetch("/api/auth/password-reset/confirm", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token, new_password: newPassword }),
      });
      setStatus(response.ok ? "success" : "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!token) {
    return <p className="text-sm text-red-600">{t("auth.resetInvalidToken")}</p>;
  }
  if (status === "success") {
    return <p className="text-sm">{t("auth.resetSuccessMessage")}</p>;
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm">
        {t("auth.resetNewPasswordLabel")}
        <Input
          type="password"
          value={newPassword}
          onChange={(event) => setNewPassword(event.target.value)}
          required
        />
      </label>
      {status === "error" && (
        <p className="text-sm text-red-600">{t("auth.resetInvalidToken")}</p>
      )}
      <Button type="submit" disabled={isSubmitting}>
        {t("auth.resetSubmitButton")}
      </Button>
    </form>
  );
}

export function ResetPasswordContent() {
  return (
    <React.Suspense fallback={null}>
      <ResetPasswordForm />
    </React.Suspense>
  );
}
