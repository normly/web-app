// frontend/src/components/app-header.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import Link from "next/link";
import { AuthDialog } from "@/components/auth/auth-dialog";
import { useAccountSession } from "@/lib/use-account-session";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { JurisdictionSwitcher } from "@/components/jurisdiction-switcher";
import { ModeToggle } from "@/components/mode-toggle";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/i18n/provider";

// getInstanceConfig() reads process.env, which is only meaningful on the
// server (and isn't inlined for the client, since these aren't NEXT_PUBLIC_
// variables -- see lib/config.ts). Callers (page.tsx) read it server-side
// and pass the result down as plain props instead of this component
// reading env vars itself.
export function AppHeader({
  instanceName,
  logoPath,
}: {
  instanceName: string;
  logoPath: string | null;
}) {
  const { t } = useTranslation();
  const { account, refreshSession, logout } = useAccountSession();

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
        <LocaleSwitcher />
        <JurisdictionSwitcher />
        <ModeToggle />
        {account ? (
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2">
              <Avatar
                avatarDataUrl={account.avatarDataUrl} firstName={account.firstName}
                lastName={account.lastName} email={account.email}
              />
              <span className="text-sm text-muted-foreground">{account.email}</span>
            </div>
            <Button variant="ghost" size="sm" onClick={logout}>
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
