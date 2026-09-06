// frontend/src/components/auth/auth-split-layout.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { useTranslation } from "@/lib/i18n/provider";
import type { TranslationKey } from "@/lib/i18n/dictionary-keys";

export function AuthSplitLayout({
  headingKey,
  descriptionKey,
  children,
}: {
  headingKey: TranslationKey;
  descriptionKey?: TranslationKey;
  children: React.ReactNode;
}) {
  const { t } = useTranslation();

  return (
    <section className="h-svh max-h-[1200px] min-h-[600px] w-full overflow-hidden bg-background">
      <div className="grid h-full lg:grid-cols-2">
        <div className="flex items-center justify-center px-6 py-12">
          <div className="flex w-full max-w-sm flex-col gap-6">
            <div className="flex flex-col gap-2">
              <h1 className="text-3xl font-semibold tracking-tight">{t(headingKey)}</h1>
              {descriptionKey && <p className="text-muted-foreground">{t(descriptionKey)}</p>}
            </div>
            {children}
          </div>
        </div>
        <div className="relative hidden bg-muted lg:block">
          <img
            src="/auth-split-photo.jpg"
            alt=""
            className="absolute inset-0 size-full object-cover"
          />
        </div>
      </div>
    </section>
  );
}
