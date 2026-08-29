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

  // The h1 lives here (rather than in page.tsx) because page.tsx is a
  // Server Component -- it calls getInstanceConfig() to feed AppHeader --
  // and this title needs useTranslation()'s client-only context.
  let body: React.ReactNode = null;
  if (requiresLogin) {
    body = <p>{t("history.loginRequired")}</p>;
  } else if (sessions !== null && sessions.length === 0) {
    body = <p>{t("history.empty")}</p>;
  } else if (sessions !== null) {
    // Not a link: full click-to-reopen session resumption (loading this
    // session's past messages into the chat UI on `/`) is real feature
    // work that hasn't been built yet -- `/` never reads a `session`
    // query param. Linking to `/?session=${session.session_token}` would
    // both do nothing and leak a live session credential into the
    // browser's address bar, history, and any access log. Plain text
    // until resumption is built.
    body = (
      <ul className="flex flex-col gap-2">
        {sessions.map((session) => (
          <li key={session.id}>{new Date(session.created_at).toLocaleDateString()}</li>
        ))}
      </ul>
    );
  }

  return (
    <>
      <h1 className="mb-4 text-xl font-semibold">{t("history.title")}</h1>
      {body}
    </>
  );
}
