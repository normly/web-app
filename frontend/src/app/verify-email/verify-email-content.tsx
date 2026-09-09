// frontend/src/app/verify-email/verify-email-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

type Status = "verifying" | "verified" | "invalid";

function VerifyEmailStatus() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [status, setStatus] = React.useState<Status>(token ? "verifying" : "invalid");
  const [resendEmail, setResendEmail] = React.useState("");
  const [resendSent, setResendSent] = React.useState(false);
  const [isResending, setIsResending] = React.useState(false);
  const hasRunRef = React.useRef(false);

  React.useEffect(() => {
    if (!token) return;
    if (hasRunRef.current) return;
    hasRunRef.current = true;
    let cancelled = false;
    fetch(`/api/auth/verify-email?token=${encodeURIComponent(token)}`)
      .then((response) => {
        if (cancelled) return;
        setStatus(response.ok ? "verified" : "invalid");
      })
      .catch(() => {
        if (!cancelled) setStatus("invalid");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const submitResend = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsResending(true);
    try {
      await fetch("/api/auth/verify-email/resend", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: resendEmail }),
      });
      setResendSent(true);
    } finally {
      setIsResending(false);
    }
  };

  if (status === "verifying") {
    return <p className="text-sm text-muted-foreground">{t("auth.verifyingMessage")}</p>;
  }
  if (status === "verified") {
    return <p className="text-sm">{t("auth.verifiedMessage")}</p>;
  }
  if (resendSent) {
    return <p className="text-sm">{t("auth.resendVerificationSentMessage")}</p>;
  }
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-destructive">{t("auth.verifyInvalidMessage")}</p>
      <form onSubmit={submitResend} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          {t("auth.emailLabel")}
          <Input
            type="email"
            value={resendEmail}
            onChange={(event) => setResendEmail(event.target.value)}
            required
          />
        </label>
        <Button type="submit" disabled={isResending}>
          {t("auth.resendVerificationButton")}
        </Button>
      </form>
    </div>
  );
}

export function VerifyEmailContent() {
  return (
    <React.Suspense fallback={null}>
      <VerifyEmailStatus />
    </React.Suspense>
  );
}
