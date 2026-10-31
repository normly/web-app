// frontend/src/app/login/login-page-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthSplitLayout } from "@/components/auth/auth-split-layout";
import { BlockedNotice } from "@/components/auth/blocked-notice";
import { LoginForm } from "@/components/auth/login-form";
import { useTranslation } from "@/lib/i18n/provider";

export function LoginPageContent({ contact }: { contact: string | null }) {
  const router = useRouter();
  const blocked = useSearchParams().get("auth_error") === "blocked";
  const { t } = useTranslation();

  return (
    <AuthSplitLayout headingKey="auth.loginPageHeading" descriptionKey="auth.loginPageDescription">
      {blocked && <BlockedNotice contact={contact} />}
      <LoginForm onSuccess={() => router.push("/")} contact={contact} />
      <a
        href="/api/auth/google/login"
        className="text-center text-sm text-muted-foreground hover:text-foreground"
      >
        {t("auth.googleButton")}
      </a>
      <p className="text-sm text-muted-foreground">
        {t("auth.magicLinkPromptText")}{" "}
        <Link href="/magic-link" className="font-medium text-primary hover:underline">
          {t("auth.magicLinkTab")}
        </Link>
      </p>
      <p className="text-sm text-muted-foreground">
        {t("auth.noAccountLink")}{" "}
        <Link href="/signup" className="font-medium text-primary hover:underline">
          {t("auth.registerTab")}
        </Link>
      </p>
    </AuthSplitLayout>
  );
}
