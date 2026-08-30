// frontend/src/app/account/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppHeader } from "@/components/app-header";
import { AccountPageContent } from "./account-page-content";

export default function AccountPage() {
  const config = getInstanceConfig();
  return (
    <>
      <AppHeader instanceName={config.instanceName} logoPath={config.logoPath} />
      <main className="mx-auto max-w-2xl p-4">
        <AccountPageContent />
      </main>
    </>
  );
}
