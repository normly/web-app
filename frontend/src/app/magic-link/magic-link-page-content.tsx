// frontend/src/app/magic-link/magic-link-page-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import Link from "next/link";
import { AuthSplitLayout } from "@/components/auth/auth-split-layout";
import { MagicLinkForm } from "@/components/auth/magic-link-form";
import { useTranslation } from "@/lib/i18n/provider";

export function MagicLinkPageContent() {
  const { t } = useTranslation();

  return (
    <AuthSplitLayout
      headingKey="auth.magicLinkPageHeading"
      descriptionKey="auth.magicLinkPageDescription"
    >
      <MagicLinkForm />
      <Link
        href="/login"
        className="text-sm text-muted-foreground hover:text-foreground"
      >
        {t("auth.backToLogin")}
      </Link>
    </AuthSplitLayout>
  );
}
