// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors
//
// Split out of page.tsx (not inlined there as the task brief shows it):
// Next.js 14.2.x's App Router type-checks every page.tsx against a fixed
// whitelist of allowed exports (default, metadata, generateMetadata, ...)
// and hard-fails `next build` on any other named export -- regardless of
// its type. A named `export function ChatsPageContent` directly in
// page.tsx therefore cannot pass `npm run build`. Content and behavior are
// otherwise identical to the brief's version; only the file location
// differs, matching the standard Next.js pattern of keeping page.tsx to a
// default export and colocating the real component elsewhere.

"use client";

import * as React from "react";
import Link from "next/link";
import { useTranslation } from "@/lib/i18n/provider";

interface ChatSessionSummary {
  id: string;
  session_token: string;
  jurisdiction: string;
  language: string;
  created_at: string;
}

export function ChatsPageContent() {
  const { t } = useTranslation();
  const [sessions, setSessions] = React.useState<ChatSessionSummary[] | null>(null);
  const [requiresLogin, setRequiresLogin] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    fetch("/api/chat/sessions").then(async (response) => {
      if (cancelled) return;
      if (response.status === 401) {
        setRequiresLogin(true);
        return;
      }
      setSessions(await response.json());
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (requiresLogin) {
    return <p>{t("history.loginRequired")}</p>;
  }
  if (sessions === null) {
    return null;
  }
  if (sessions.length === 0) {
    return <p>{t("history.empty")}</p>;
  }

  return (
    <ul className="flex flex-col gap-2">
      {sessions.map((session) => (
        <li key={session.id}>
          <Link href={`/?session=${session.session_token}`} className="underline">
            {new Date(session.created_at).toLocaleDateString()}
          </Link>
        </li>
      ))}
    </ul>
  );
}
