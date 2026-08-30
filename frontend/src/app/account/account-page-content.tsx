// frontend/src/app/account/account-page-content.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors
//
// Deliberately thin: fetches the account once, renders section components.
// Tasks 11-14 each add one import and one <XSection ... /> line here, after
// <NameAvatarSection ... /> -- never reproduce this whole file in a later
// task's brief, only the small addition.

"use client";

import * as React from "react";
import { NameAvatarSection } from "@/components/account/name-avatar-section";
import { EmailSection } from "@/components/account/email-section";
import { PasswordSection } from "@/components/account/password-section";
import { SessionsSection } from "@/components/account/sessions-section";
import { useTranslation } from "@/lib/i18n/provider";
import type { AccountSummary } from "@/lib/account-response";

export function AccountPageContent() {
  const { t } = useTranslation();
  const [account, setAccount] = React.useState<AccountSummary | null>(null);
  const [requiresLogin, setRequiresLogin] = React.useState(false);

  React.useEffect(() => {
    fetch("/api/auth/session")
      .then((response) => response.json())
      .then((body: { account: AccountSummary | null }) => {
        if (body.account === null) {
          setRequiresLogin(true);
        } else {
          setAccount(body.account);
        }
      })
      .catch(() => setRequiresLogin(true));
  }, []);

  if (requiresLogin) {
    return <p>{t("account.loginRequired")}</p>;
  }
  if (account === null) {
    return null;
  }

  return (
    <div className="flex flex-col gap-8">
      <h1 className="text-xl font-semibold">{t("account.pageTitle")}</h1>
      <NameAvatarSection account={account} onAccountUpdated={setAccount} />
      <EmailSection account={account} />
      <PasswordSection />
      <SessionsSection />
    </div>
  );
}
