// frontend/src/components/auth/blocked-notice.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { useTranslation } from "@/lib/i18n/provider";

// An e-mail address becomes a mailto: link, an http(s) URL (e.g. the imprint)
// a normal link; anything else stays plain text.
function contactHref(contact: string): string | null {
  if (/^https?:\/\//i.test(contact)) return contact;
  if (contact.includes("@") && !contact.includes("://")) return `mailto:${contact}`;
  return null;
}

// Neutral on purpose: no reason, only where to ask (ADR-030).
export function BlockedNotice({ contact }: { contact: string | null }) {
  const { t } = useTranslation();
  const href = contact ? contactHref(contact) : null;
  const [before, after = ""] = t("auth.accountBlockedContact").split("{contact}");
  return (
    <div role="alert" className="rounded-md border border-destructive p-3 text-sm">
      <p>{t("auth.accountBlocked")}</p>
      {contact && (
        <p className="mt-1">
          {before}
          {href ? <a href={href} className="underline">{contact}</a> : contact}
          {after}
        </p>
      )}
    </div>
  );
}
