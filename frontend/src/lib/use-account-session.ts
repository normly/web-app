// frontend/src/lib/use-account-session.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import type { AccountSummary } from "@/lib/account-response";

export function useAccountSession() {
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

  const logout = React.useCallback(async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      setAccount(null);
    }
  }, []);

  return { account, refreshSession, logout, setAccount };
}
