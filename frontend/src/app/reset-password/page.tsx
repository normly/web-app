// frontend/src/app/reset-password/page.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { getInstanceConfig } from "@/lib/config";
import { AppHeader } from "@/components/app-header";
import { ResetPasswordContent } from "./reset-password-content";

export default function ResetPasswordPage() {
  const config = getInstanceConfig();
  return (
    <>
      <AppHeader
        instanceName={config.instanceName} logoPath={config.logoPath}
        showHistoryLink={false}
      />
      <main className="mx-auto max-w-2xl p-4">
        <ResetPasswordContent />
      </main>
    </>
  );
}
