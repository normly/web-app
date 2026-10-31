// frontend/src/components/auth/blocked-notice.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { useTranslation } from "@/lib/i18n/provider";
import { interpolate } from "@/lib/i18n/interpolate";

// Neutral on purpose: no reason, only where to ask (ADR-030).
export function BlockedNotice({ contact }: { contact: string | null }) {
  const { t } = useTranslation();
  return (
    <div role="alert" className="rounded-md border border-destructive p-3 text-sm">
      <p>{t("auth.accountBlocked")}</p>
      {contact && <p className="mt-1">{interpolate(t("auth.accountBlockedContact"), { contact })}</p>}
    </div>
  );
}
