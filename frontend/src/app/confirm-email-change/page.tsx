// frontend/src/app/confirm-email-change/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppHeader } from "@/components/app-header";
import { ConfirmEmailChangeContent } from "./confirm-email-change-content";

export default function ConfirmEmailChangePage() {
  const config = getInstanceConfig();
  return (
    <>
      <AppHeader instanceName={config.instanceName} logoPath={config.logoPath} />
      <main className="mx-auto max-w-2xl p-4">
        <ConfirmEmailChangeContent />
      </main>
    </>
  );
}
