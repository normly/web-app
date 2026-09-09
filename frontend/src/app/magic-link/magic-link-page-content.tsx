// frontend/src/app/magic-link/magic-link-page-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthSplitLayout } from "@/components/auth/auth-split-layout";
import { MagicLinkForm } from "@/components/auth/magic-link-form";
import { useTranslation } from "@/lib/i18n/provider";

function MagicLinkConfirm({ token }: { token: string }) {
  const router = useRouter();
  const { t } = useTranslation();
  const [status, setStatus] = React.useState<"confirming" | "error">("confirming");
  const hasRunRef = React.useRef(false);

  React.useEffect(() => {
    if (hasRunRef.current) return;
    hasRunRef.current = true;
    let cancelled = false;
    fetch("/api/auth/magic-link/confirm", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ token }),
    })
      .then((response) => {
        if (cancelled) return;
        if (response.ok) {
          router.push("/");
        } else {
          setStatus("error");
        }
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [token, router]);

  if (status === "error") {
    return <p className="text-sm text-destructive">{t("auth.magicLinkInvalidMessage")}</p>;
  }
  return <p className="text-sm text-muted-foreground">{t("auth.magicLinkConfirmingMessage")}</p>;
}

function MagicLinkPageBody() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  return (
    <AuthSplitLayout
      headingKey="auth.magicLinkPageHeading"
      descriptionKey={token ? undefined : "auth.magicLinkPageDescription"}
    >
      {token ? (
        <MagicLinkConfirm token={token} />
      ) : (
        <>
          <MagicLinkForm />
          <Link
            href="/login"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            {t("auth.backToLogin")}
          </Link>
        </>
      )}
    </AuthSplitLayout>
  );
}

export function MagicLinkPageContent() {
  return (
    <React.Suspense fallback={null}>
      <MagicLinkPageBody />
    </React.Suspense>
  );
}
