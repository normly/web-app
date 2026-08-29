// frontend/src/components/app-header.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import Link from "next/link";
import { AuthDialog } from "@/components/auth/auth-dialog";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { JurisdictionSwitcher } from "@/components/jurisdiction-switcher";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

interface AccountSummary {
  accountId: string;
  email: string;
}

// getInstanceConfig() reads process.env, which is only meaningful on the
// server (and isn't inlined for the client, since these aren't NEXT_PUBLIC_
// variables -- see lib/config.ts). Callers (page.tsx, chats/page.tsx) read
// it server-side and pass the result down as plain props instead of this
// component reading env vars itself.
export function AppHeader({
  instanceName,
  logoPath,
  showHistoryLink = true,
}: {
  instanceName: string;
  logoPath: string | null;
  showHistoryLink?: boolean;
}) {
  const { t } = useTranslation();
  const [account, setAccount] = React.useState<AccountSummary | null>(null);

  const refreshSession = React.useCallback(() => {
    fetch("/api/auth/session")
      .then((response) => response.json())
      .then((body: { account: AccountSummary | null }) => setAccount(body.account))
      .catch(() => setAccount(null));
  }, []);

  React.useEffect(() => {
    refreshSession();
  }, [refreshSession]);

  const handleLogout = async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      setAccount(null);
    }
  };

  return (
    <header className="flex items-center justify-between border-b p-4">
      {logoPath ? (
        <img src={logoPath} alt={instanceName} className="h-6" />
      ) : (
        <span className="font-semibold">{instanceName}</span>
      )}
      <div className="flex items-center gap-2">
        <Link href="/search" className="text-sm underline">
          {t("search.navLink")}
        </Link>
        {showHistoryLink && (
          <Link href="/chats" className="text-sm underline">
            {t("chat.historyLink")}
          </Link>
        )}
        <LocaleSwitcher />
        <JurisdictionSwitcher />
        {account ? (
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">{account.email}</span>
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              {t("auth.logoutButton")}
            </Button>
          </div>
        ) : (
          <AuthDialog onAuthenticated={refreshSession} />
        )}
      </div>
    </header>
  );
}
