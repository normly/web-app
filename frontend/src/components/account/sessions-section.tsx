// frontend/src/components/account/sessions-section.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

interface SessionSummary {
  id: string;
  createdAt: string;
  expiresAt: string;
  isCurrent: boolean;
}

interface RawSessionSummary {
  id: string;
  created_at: string;
  expires_at: string;
  is_current: boolean;
}

export function SessionsSection() {
  const { t, locale } = useTranslation();
  const [sessions, setSessions] = React.useState<SessionSummary[] | null>(null);

  const load = React.useCallback(() => {
    fetch("/api/account/sessions")
      .then((response) => response.json())
      .then((raw: RawSessionSummary[]) =>
        setSessions(
          raw.map((s) => ({
            id: s.id, createdAt: s.created_at, expiresAt: s.expires_at, isCurrent: s.is_current,
          })),
        ),
      );
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const revoke = async (sessionId: string) => {
    const response = await fetch(`/api/account/sessions/${sessionId}`, { method: "DELETE" });
    if (response.ok) {
      setSessions((current) => (current ?? []).filter((s) => s.id !== sessionId));
    }
  };

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{t("account.sessionsTitle")}</h2>
      <ul className="flex flex-col gap-2">
        {(sessions ?? []).map((session) => (
          <li key={session.id} className="flex items-center justify-between gap-3 text-sm">
            <span>
              {t("account.sessionCreatedLabel")}{" "}
              {new Date(session.createdAt).toLocaleDateString(locale)}
              {session.isCurrent && (
                <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs">
                  {t("account.sessionCurrentBadge")}
                </span>
              )}
            </span>
            {!session.isCurrent && (
              <Button variant="ghost" size="sm" onClick={() => revoke(session.id)}>
                {t("account.revokeSessionButton")}
              </Button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
