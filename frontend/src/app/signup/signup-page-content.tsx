// frontend/src/app/signup/signup-page-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { RegisterForm } from "@/components/auth/register-form";
import { useTranslation } from "@/lib/i18n/provider";

export function SignupPageContent() {
  const router = useRouter();
  const { t } = useTranslation();

  return (
    <section className="flex h-svh w-full items-center justify-center bg-muted px-6 py-12">
      <div className="flex w-full max-w-sm flex-col items-center gap-6">
        <h1 className="text-xl font-semibold">{t("auth.signupPageHeading")}</h1>
        <div className="w-full rounded-md border bg-background p-6 shadow-md">
          <RegisterForm onSuccess={() => router.push("/")} />
        </div>
        <p className="flex gap-1 text-sm text-muted-foreground">
          {t("auth.haveAccountLink")}
          <Link href="/login" className="font-medium text-primary hover:underline">
            {t("auth.loginTab")}
          </Link>
        </p>
      </div>
    </section>
  );
}
