// frontend/src/app/confirm-email-change/confirm-email-change-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { useTranslation } from "@/lib/i18n/provider";

function ConfirmEmailChangeInner() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const email = searchParams.get("email") ?? "";
  const [status, setStatus] = React.useState<"pending" | "success" | "error">("pending");

  React.useEffect(() => {
    if (!token || !email) {
      setStatus("error");
      return;
    }
    fetch(`/api/account/email/confirm?token=${encodeURIComponent(token)}&email=${email}`)
      .then((response) => setStatus(response.ok ? "success" : "error"))
      .catch(() => setStatus("error"));
  }, [token, email]);

  if (status === "pending") {
    return null;
  }
  if (status === "success") {
    return <p className="text-sm">{t("account.confirmEmailChangeSuccessMessage")}</p>;
  }
  return <p className="text-sm text-red-600">{t("account.confirmEmailChangeErrorMessage")}</p>;
}

export function ConfirmEmailChangeContent() {
  return (
    <React.Suspense fallback={null}>
      <ConfirmEmailChangeInner />
    </React.Suspense>
  );
}
