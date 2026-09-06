// frontend/src/app/login/login-page-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthSplitLayout } from "@/components/auth/auth-split-layout";
import { LoginForm } from "@/components/auth/login-form";
import { useTranslation } from "@/lib/i18n/provider";

export function LoginPageContent() {
  const router = useRouter();
  const { t } = useTranslation();

  return (
    <AuthSplitLayout headingKey="auth.loginPageHeading" descriptionKey="auth.loginPageDescription">
      <LoginForm onSuccess={() => router.push("/")} />
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
